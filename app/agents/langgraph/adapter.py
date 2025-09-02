"""
LangGraph 어댑터

기존 에이전트 시스템과 LangGraph 시스템을 연결하는 어댑터입니다.
점진적 마이그레이션과 호환성을 지원합니다.
"""

from typing import Dict, Any, Optional, Union
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.config import settings
from app.agents.schemas import AgentContext, UserModelPreferences
from app.agents.core.base_agent import AgentResponse

from .graphs.content_processing_graph import content_processing_graph

logger = get_logger(__name__)


class AgentMode(Enum):
    """에이전트 실행 모드"""
    LEGACY = "legacy"      # 기존 V1 시스템
    LANGGRAPH = "langgraph"  # 새로운 LangGraph 시스템
    AUTO = "auto"          # 자동 선택


class LangGraphAgentAdapter:
    """LangGraph 에이전트 어댑터"""
    
    def __init__(self):
        self.default_mode = AgentMode.AUTO
        self.execution_stats = {
            "legacy_executions": 0,
            "langgraph_executions": 0,
            "auto_selections": {
                "legacy": 0,
                "langgraph": 0
            }
        }
    
    async def process_content(self,
                            user_id: int,
                            input_data: Dict[str, Any],
                            context: AgentContext,
                            mode: Optional[Union[AgentMode, str]] = None,
                            session: Optional[AsyncSession] = None) -> AgentResponse:
        """
        통합 콘텐츠 처리 인터페이스
        
        Args:
            user_id: 사용자 ID
            input_data: 입력 데이터
            context: 에이전트 컨텍스트
            mode: 실행 모드 (legacy, langgraph, auto)
            session: 데이터베이스 세션
            
        Returns:
            통합된 AgentResponse 형식의 결과
        """
        # 모드 결정
        execution_mode = await self._determine_execution_mode(mode, context, input_data)
        
        logger.info(f"Processing content with mode: {execution_mode.value} for user {user_id}")
        
        try:
            if execution_mode == AgentMode.LANGGRAPH:
                return await self._execute_langgraph(user_id, input_data, context, session)
            else:
                return await self._execute_legacy(user_id, input_data, context, session)
                
        except Exception as e:
            logger.error(f"Content processing failed in {execution_mode.value} mode: {e}")
            # 폴백: 다른 모드로 재시도
            if execution_mode == AgentMode.LANGGRAPH:
                logger.info("Falling back to legacy mode")
                return await self._execute_legacy(user_id, input_data, context, session)
            else:
                raise
    
    async def _determine_execution_mode(self,
                                       mode: Optional[Union[AgentMode, str]],
                                       context: AgentContext,
                                       input_data: Dict[str, Any]) -> AgentMode:
        """실행 모드 결정"""
        if mode:
            if isinstance(mode, str):
                mode = AgentMode(mode.lower())
            
            if mode != AgentMode.AUTO:
                return mode
        
        # AUTO 모드: 자동 선택 로직
        # 복잡도나 사용자 선호도에 따라 결정
        
        # LangGraph를 사용할 조건들
        use_langgraph = (
            context.complexity >= 3 or  # 복잡한 작업
            context.user_model_preferences.quality_preference == "quality" or  # 품질 중시
            len(input_data.get("similar_tags", [])) > 0 or  # 기존 태그 고려 필요
            input_data.get("content_type") == "youtube"  # YouTube 콘텐츠
        )
        
        selected_mode = AgentMode.LANGGRAPH if use_langgraph else AgentMode.LEGACY
        
        # 통계 업데이트
        self.execution_stats["auto_selections"][selected_mode.value] += 1
        
        logger.info(f"Auto-selected mode: {selected_mode.value} (complexity={context.complexity}, quality_pref={context.user_model_preferences.quality_preference})")
        
        return selected_mode
    
    async def _execute_langgraph(self,
                               user_id: int,
                               input_data: Dict[str, Any],
                               context: AgentContext,
                               session: Optional[AsyncSession]) -> AgentResponse:
        """LangGraph 시스템으로 실행"""
        self.execution_stats["langgraph_executions"] += 1
        
        # LangGraph 워크플로우 실행
        result = await content_processing_graph.process_content(
            user_id=user_id,
            input_data=input_data,
            context=context,
            session=session
        )
        
        # AgentResponse 형식으로 변환
        return self._convert_langgraph_result_to_agent_response(result)
    
    async def _execute_legacy(self,
                            user_id: int,
                            input_data: Dict[str, Any],
                            context: AgentContext,
                            session: Optional[AsyncSession]) -> AgentResponse:
        """레거시 시스템으로 실행"""
        self.execution_stats["legacy_executions"] += 1
        
        # 기존 에이전트 시스템 사용
        # 여기서는 간단한 더미 구현 (실제로는 기존 specialized 에이전트들을 사용)
        from app.agents.specialized.content_agent import ContentAgent
        
        content_agent = ContentAgent()
        return await content_agent.process_with_wtu(input_data, context, session)
    
    def _convert_langgraph_result_to_agent_response(self, result: Dict[str, Any]) -> AgentResponse:
        """LangGraph 결과를 AgentResponse로 변환"""
        success = result.get("success", False)
        
        if not success:
            return AgentResponse(
                content=result.get("error", "알 수 없는 오류가 발생했습니다."),
                success=False,
                error_message=result.get("error"),
                metadata={
                    "execution_mode": "langgraph",
                    "workflow_type": "content_processing"
                }
            )
        
        # 성공한 경우
        execution_stats = result.get("execution_stats", {})
        detailed_results = result.get("detailed_results", {})
        
        # 주요 결과 추출
        summary = result.get("summary", "")
        tags = result.get("tags", [])
        category = result.get("category", "")
        
        # 메인 콘텐츠 구성
        main_content = {
            "summary": summary,
            "tags": tags,
            "category": category,
            "validation_passed": result.get("validation_passed", True),
            "validation_score": result.get("validation_score", 1.0)
        }
        
        # 메타데이터 구성
        metadata = {
            "execution_mode": "langgraph",
            "workflow_type": "content_processing",
            "validation_enabled": "validation" in detailed_results,
            "nodes_executed": list(detailed_results.keys()),
            **execution_stats
        }
        
        return AgentResponse(
            content=main_content,
            metadata=metadata,
            model_used="multi_agent_langgraph",
            tokens_used={
                "total": execution_stats.get("total_tokens_used", 0)
            },
            wtu_consumed=execution_stats.get("total_wtu_consumed", 0.0),
            cost_usd=execution_stats.get("total_cost_usd", 0.0),
            execution_time_ms=int(execution_stats.get("execution_time_seconds", 0) * 1000),
            success=True
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """실행 통계 반환"""
        total_executions = (self.execution_stats["legacy_executions"] + 
                          self.execution_stats["langgraph_executions"])
        
        return {
            "total_executions": total_executions,
            "legacy_executions": self.execution_stats["legacy_executions"],
            "langgraph_executions": self.execution_stats["langgraph_executions"],
            "langgraph_adoption_rate": (
                self.execution_stats["langgraph_executions"] / total_executions 
                if total_executions > 0 else 0
            ),
            "auto_selection_stats": self.execution_stats["auto_selections"]
        }
    
    def set_default_mode(self, mode: Union[AgentMode, str]):
        """기본 실행 모드 설정"""
        if isinstance(mode, str):
            mode = AgentMode(mode.lower())
        self.default_mode = mode
        logger.info(f"Default agent mode set to: {mode.value}")


# 전역 어댑터 인스턴스
agent_adapter = LangGraphAgentAdapter()


# 편의 함수들
async def process_content_with_langgraph(
    user_id: int,
    input_data: Dict[str, Any],
    context: AgentContext,
    mode: Optional[str] = None,
    session: Optional[AsyncSession] = None
) -> AgentResponse:
    """
    콘텐츠 처리 편의 함수
    
    Args:
        user_id: 사용자 ID
        input_data: 입력 데이터
        context: 에이전트 컨텍스트
        mode: 실행 모드 ("legacy", "langgraph", "auto")
        session: 데이터베이스 세션
        
    Returns:
        처리 결과
    """
    return await agent_adapter.process_content(
        user_id=user_id,
        input_data=input_data,
        context=context,
        mode=mode,
        session=session
    )


def get_agent_statistics() -> Dict[str, Any]:
    """에이전트 실행 통계 조회"""
    return agent_adapter.get_statistics()


def configure_agent_mode(mode: str):
    """에이전트 기본 모드 설정"""
    agent_adapter.set_default_mode(mode)