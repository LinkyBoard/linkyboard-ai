"""
Base Agent Class - WTU 통합 에이전트 기본 클래스

모든 AI 에이전트가 상속받는 기본 클래스로, WTU 자동 추적 및 모니터링 기능을 제공합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime
from dataclasses import dataclass
from uuid import uuid4, UUID

from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.logging import get_logger
from app.metrics import record_llm_usage, calculate_llm_wtu
from app.metrics.model_catalog_service import model_catalog_service
from app.ai.providers.router import ai_router
from app.core.utils.observability import trace_ai_operation, record_ai_tokens, record_wtu_usage
from ..schemas import AgentContext, UserModelPreferences

logger = get_logger(__name__)


@dataclass
class WTUSession:
    """WTU 추적 세션"""
    session_id: str
    user_id: int
    agent_type: str
    model_name: str
    start_time: datetime
    input_tokens: int = 0
    output_tokens: int = 0
    wtu_consumed: float = 0.0
    cost_usd: float = 0.0
    success: bool = False
    error_message: Optional[str] = None
    

class AgentResponse(BaseModel):
    """에이전트 응답"""
    content: Union[str, Dict[str, Any]]
    metadata: Dict[str, Any] = {}
    model_used: str = ""
    tokens_used: Dict[str, int] = {}
    wtu_consumed: float = 0.0
    cost_usd: float = 0.0
    execution_time_ms: int = 0
    quality_score: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class AIAgent(ABC):
    """
    AI 에이전트 기본 클래스
    
    모든 에이전트가 상속받아야 하는 추상 클래스로, WTU 자동 추적 및 
    사용자 선택 모델 기반 실행을 지원합니다.
    """
    
    def __init__(self, agent_name: str, default_model: str = "gpt-4o-mini"):
        self.agent_name = agent_name
        self.default_model = default_model
        self.execution_count = 0
        
    @abstractmethod
    def get_agent_type(self) -> str:
        """에이전트 타입 반환 (예: content_analysis, summary_generation)"""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """에이전트가 수행할 수 있는 작업 목록 반환"""
        pass
    
    @abstractmethod
    async def validate_input(self, input_data: Dict[str, Any], context: AgentContext) -> bool:
        """입력 데이터 유효성 검증"""
        pass
    
    @abstractmethod
    async def execute_ai_task(
        self, 
        input_data: Dict[str, Any], 
        model_name: str,
        context: AgentContext
    ) -> Dict[str, Any]:
        """실제 AI 작업 실행 (하위 클래스에서 구현)"""
        pass
    
    async def process_with_wtu(
        self, 
        input_data: Dict[str, Any], 
        context: AgentContext,
        session: Optional[AsyncSession] = None
    ) -> AgentResponse:
        """
        WTU 추적을 포함한 에이전트 처리
        
        Args:
            input_data: 입력 데이터
            context: 에이전트 실행 컨텍스트  
            session: 데이터베이스 세션
            
        Returns:
            처리 결과와 WTU 정보가 포함된 응답
        """
        start_time = datetime.now()
        execution_id = str(uuid4())
        
        # 입력 검증
        if not await self.validate_input(input_data, context):
            return AgentResponse(
                content="입력 데이터가 유효하지 않습니다.",
                success=False,
                error_message="Invalid input data"
            )
        
        try:
            # 1. 사용자 선택 모델 결정
            selected_model = await self._select_optimal_model(
                context.user_model_preferences,
                context.complexity
            )
            
            logger.info(
                f"Agent {self.agent_name} starting execution with model {selected_model} "
                f"for user {context.user_id}"
            )
            
            # 2. WTU 세션 시작
            wtu_session = WTUSession(
                session_id=execution_id,
                user_id=context.user_id,
                agent_type=self.get_agent_type(),
                model_name=selected_model,
                start_time=start_time
            )
            
            # 3. AI 작업 실행 (OpenTelemetry 추적 포함)
            async with trace_ai_operation(
                model=selected_model,
                operation=f"agent_{self.get_agent_type()}",
                user_id=context.user_id,
                board_id=context.board_id,
                agent_execution_id=execution_id
            ) as span:
                
                result = await self.execute_ai_task(
                    input_data=input_data,
                    model_name=selected_model,
                    context=context
                )
                
                # 4. 토큰 사용량 추출
                input_tokens = result.get('usage', {}).get('input_tokens', 0)
                output_tokens = result.get('usage', {}).get('output_tokens', 0)
                
                # OpenTelemetry에 토큰 기록
                await record_ai_tokens(selected_model, input_tokens, output_tokens)
                
                # 5. WTU 계산 및 기록
                wtu_consumed, cost_usd = await self._calculate_and_record_wtu(
                    wtu_session=wtu_session,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model_name=selected_model,
                    board_id=context.board_id,
                    session=session
                )
                
                # OpenTelemetry에 WTU 기록
                await record_wtu_usage(context.user_id, selected_model, wtu_consumed)
                
                # 6. 실행 통계 업데이트
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                self.execution_count += 1
                
                # 7. 성공 응답 생성
                response = AgentResponse(
                    content=result.get('content', ''),
                    metadata={
                        'agent_name': self.agent_name,
                        'agent_type': self.get_agent_type(),
                        'execution_id': execution_id,
                        'model_selection_reason': result.get('model_selection_reason', 'user_preference'),
                        **result.get('metadata', {})
                    },
                    model_used=selected_model,
                    tokens_used={
                        'input': input_tokens,
                        'output': output_tokens,
                        'total': input_tokens + output_tokens
                    },
                    wtu_consumed=wtu_consumed,
                    cost_usd=cost_usd,
                    execution_time_ms=int(execution_time),
                    success=True
                )
                
                logger.info(
                    f"Agent {self.agent_name} completed successfully: "
                    f"WTU={wtu_consumed:.3f}, cost=${cost_usd:.4f}, time={execution_time:.1f}ms"
                )
                
                return response
                
        except Exception as e:
            error_message = str(e)
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            logger.error(
                f"Agent {self.agent_name} execution failed: {error_message} "
                f"(execution_time={execution_time:.1f}ms)"
            )
            
            return AgentResponse(
                content=f"에이전트 실행 중 오류가 발생했습니다: {error_message}",
                metadata={
                    'agent_name': self.agent_name,
                    'agent_type': self.get_agent_type(),
                    'execution_id': execution_id,
                    'error_details': error_message
                },
                execution_time_ms=int(execution_time),
                success=False,
                error_message=error_message
            )
    
    async def _select_optimal_model(
        self,
        user_preferences: UserModelPreferences,
        complexity: int
    ) -> str:
        """
        사용자 선호도와 작업 복잡도를 고려한 최적 모델 선택
        """
        try:
            # 1. 사용자 기본 모델이 설정되어 있으면 우선 사용
            if user_preferences.default_llm_model:
                model_catalog = await model_catalog_service.get_model_catalog(
                    user_preferences.default_llm_model
                )
                if model_catalog and model_catalog.is_active:
                    return user_preferences.default_llm_model
            
            # 2. 활성 LLM 모델들 조회
            available_models = await model_catalog_service.get_active_models("llm")
            
            if not available_models:
                logger.warning("No active LLM models found, using default")
                return self.default_model
            
            # 3. 사용자 선호도에 따른 모델 필터링
            if user_preferences.preferred_providers:
                filtered_models = [
                    model for model in available_models 
                    if model.provider in user_preferences.preferred_providers
                ]
                if filtered_models:
                    available_models = filtered_models
            
            # 피할 모델 제외
            if user_preferences.avoid_models:
                available_models = [
                    model for model in available_models
                    if model.model_name not in user_preferences.avoid_models
                ]
            
            # 4. 복잡도와 품질 선호도에 따른 모델 선택
            if complexity >= 4 or user_preferences.quality_preference == "quality":
                # 고품질 모델 우선
                high_quality_models = [
                    model for model in available_models
                    if model.model_name in ["gpt-4o", "claude-3.5-sonnet", "gemini-1.5-pro"]
                ]
                if high_quality_models:
                    return high_quality_models[0].model_name
            
            if complexity <= 2 or user_preferences.quality_preference == "speed":
                # 빠른 모델 우선  
                fast_models = [
                    model for model in available_models
                    if model.model_name in ["gpt-4o-mini", "claude-3-haiku", "gemini-1.5-flash"]
                ]
                if fast_models:
                    return fast_models[0].model_name
            
            # 5. 기본적으로 가장 비용 효율적인 모델 선택
            if user_preferences.cost_sensitivity == "high":
                available_models.sort(key=lambda x: x.weight_input + x.weight_output)
                return available_models[0].model_name
            
            # 6. 폴백: 기본 모델
            return self.default_model
            
        except Exception as e:
            logger.warning(f"Model selection failed: {e}, using default model")
            return self.default_model
    
    async def _calculate_and_record_wtu(
        self,
        wtu_session: WTUSession,
        input_tokens: int,
        output_tokens: int,
        model_name: str,
        board_id: Optional[int] = None,
        session: Optional[AsyncSession] = None
    ) -> Tuple[float, float]:
        """
        WTU 계산 및 데이터베이스 기록
        """
        try:
            # WTU 계산
            wtu_consumed = await calculate_llm_wtu(
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                session=session
            )
            
            # 사용량 기록
            usage_record = await record_llm_usage(
                user_id=wtu_session.user_id,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                board_id=board_id,
                session=session
            )
            
            # 비용 계산 (모델 카탈로그에서 가격 정보 조회)
            cost_usd = 0.0
            model_catalog = await model_catalog_service.get_model_catalog(model_name, session)
            if model_catalog:
                input_cost = (input_tokens / 1_000_000) * (model_catalog.price_input or 0)
                output_cost = (output_tokens / 1_000_000) * (model_catalog.price_output or 0)
                cost_usd = input_cost + output_cost
            
            # WTU 세션 업데이트
            wtu_session.input_tokens = input_tokens
            wtu_session.output_tokens = output_tokens
            wtu_session.wtu_consumed = wtu_consumed
            wtu_session.cost_usd = cost_usd
            wtu_session.success = True
            
            logger.debug(
                f"WTU calculation completed: {wtu_consumed:.3f} WTU, "
                f"${cost_usd:.4f} USD, {input_tokens}+{output_tokens} tokens"
            )
            
            return wtu_consumed, cost_usd
            
        except Exception as e:
            logger.error(f"WTU calculation failed: {e}")
            wtu_session.error_message = str(e)
            return 0.0, 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """에이전트 실행 통계 반환"""
        return {
            'agent_name': self.agent_name,
            'agent_type': self.get_agent_type(),
            'execution_count': self.execution_count,
            'capabilities': self.get_capabilities()
        }