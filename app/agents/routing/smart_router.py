"""
Smart Router - 스마트 라우터

사용자 요청을 V1 (Legacy) 또는 V2 (Agent) 시스템으로 라우팅합니다.
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.database import AsyncSessionLocal
from ..schemas import ProcessingModeRequest, ProcessingModeResponse, AgentContext
from ..mode_selector import mode_selector_service
from ..core.coordinator import agent_coordinator
from ..core.context_manager import context_manager
from .legacy_adapter import LegacyAdapter

logger = get_logger(__name__)


@dataclass
class RoutingDecision:
    """라우팅 결정"""
    selected_mode: str  # 'legacy' or 'agent'
    reason: str
    confidence: float
    estimated_time_seconds: int
    estimated_wtu: float
    fallback_available: bool


@dataclass
class RoutingResult:
    """라우팅 결과"""
    mode_used: str
    processing_result: Dict[str, Any]
    execution_time_ms: int
    wtu_consumed: float
    success: bool
    error_message: Optional[str] = None
    fallback_used: bool = False


class SmartRouter:
    """스마트 라우터"""
    
    def __init__(self):
        self.legacy_adapter = LegacyAdapter()
        self.routing_stats = {
            'total_requests': 0,
            'legacy_count': 0,
            'agent_count': 0,
            'fallback_count': 0,
            'success_rate_by_mode': {
                'legacy': {'success': 0, 'total': 0},
                'agent': {'success': 0, 'total': 0}
            }
        }
        
    async def route_request(
        self,
        request_type: str,
        request_data: Dict[str, Any],
        user_id: int,
        board_id: Optional[int] = None,
        processing_mode: str = "auto",
        session: Optional[AsyncSession] = None
    ) -> RoutingResult:
        """
        요청을 적절한 처리 모드로 라우팅
        
        Args:
            request_type: 요청 타입 (board_analysis, clipper, summary 등)
            request_data: 요청 데이터
            user_id: 사용자 ID
            board_id: 보드 ID (선택사항)
            processing_mode: 처리 모드 ("legacy", "agent", "auto")
            session: DB 세션
            
        Returns:
            라우팅 및 처리 결과
        """
        start_time = datetime.now()
        self.routing_stats['total_requests'] += 1
        
        try:
            logger.info(f"Routing request: type={request_type}, mode={processing_mode}, user={user_id}")
            
            # 1. 처리 모드 결정
            mode_decision = await self._determine_processing_mode(
                request_type=request_type,
                request_data=request_data,
                user_id=user_id,
                board_id=board_id,
                processing_mode=processing_mode
            )
            
            logger.info(
                f"Mode decision: {mode_decision.selected_mode} "
                f"(confidence: {mode_decision.confidence:.2f}, reason: {mode_decision.reason})"
            )
            
            # 2. 선택된 모드로 처리 실행
            processing_result = None
            fallback_used = False
            
            try:
                if mode_decision.selected_mode == "agent":
                    processing_result = await self._process_with_agents(
                        request_type=request_type,
                        request_data=request_data,
                        user_id=user_id,
                        board_id=board_id,
                        session=session
                    )
                    self.routing_stats['agent_count'] += 1
                    
                else:  # legacy
                    processing_result = await self._process_with_legacy(
                        request_type=request_type,
                        request_data=request_data,
                        user_id=user_id,
                        board_id=board_id,
                        session=session
                    )
                    self.routing_stats['legacy_count'] += 1
                    
            except Exception as mode_error:
                logger.error(f"Primary mode {mode_decision.selected_mode} failed: {mode_error}")
                
                # 3. 폴백 처리 (Agent 모드 실패시 Legacy로 전환)
                if mode_decision.selected_mode == "agent" and mode_decision.fallback_available:
                    logger.info("Attempting fallback to legacy mode")
                    
                    try:
                        processing_result = await self._process_with_legacy(
                            request_type=request_type,
                            request_data=request_data,
                            user_id=user_id,
                            board_id=board_id,
                            session=session
                        )
                        fallback_used = True
                        self.routing_stats['fallback_count'] += 1
                        logger.info("Fallback to legacy mode successful")
                        
                    except Exception as fallback_error:
                        logger.error(f"Fallback also failed: {fallback_error}")
                        raise fallback_error
                else:
                    raise mode_error
            
            # 4. 처리 결과 분석
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            success = processing_result and processing_result.get('success', True)
            
            # 통계 업데이트
            mode_used = mode_decision.selected_mode if not fallback_used else "legacy"
            self._update_success_stats(mode_used, success)
            
            # 5. 최종 결과 반환
            return RoutingResult(
                mode_used=mode_used,
                processing_result=processing_result or {},
                execution_time_ms=int(execution_time),
                wtu_consumed=processing_result.get('wtu_consumed', 0.0),
                success=success,
                fallback_used=fallback_used
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Request routing failed: {e}")
            
            return RoutingResult(
                mode_used="error",
                processing_result={},
                execution_time_ms=int(execution_time),
                wtu_consumed=0.0,
                success=False,
                error_message=str(e)
            )
    
    async def _determine_processing_mode(
        self,
        request_type: str,
        request_data: Dict[str, Any],
        user_id: int,
        board_id: Optional[int],
        processing_mode: str
    ) -> RoutingDecision:
        """처리 모드 결정"""
        try:
            # ProcessingModeService 사용
            mode_request = ProcessingModeRequest(
                mode=processing_mode,
                user_id=user_id,
                board_id=board_id,
                task_type=request_type,
                complexity_preference=request_data.get('complexity_preference', 'balanced'),
                quality_threshold=request_data.get('quality_threshold', 0.85),
                budget_limit_wtu=request_data.get('budget_limit_wtu')
            )
            
            mode_response = await mode_selector_service.select_processing_mode(mode_request)
            
            return RoutingDecision(
                selected_mode=mode_response.selected_mode,
                reason=mode_response.reason,
                confidence=mode_response.cost_efficiency_score,
                estimated_time_seconds=mode_response.estimated_time_seconds,
                estimated_wtu=mode_response.estimated_wtu,
                fallback_available=mode_response.fallback_available
            )
            
        except Exception as e:
            logger.error(f"Mode determination failed: {e}")
            # 기본값으로 Legacy 모드 선택
            return RoutingDecision(
                selected_mode="legacy",
                reason=f"모드 결정 실패로 안전한 Legacy 모드 선택: {str(e)}",
                confidence=0.8,
                estimated_time_seconds=30,
                estimated_wtu=2.0,
                fallback_available=False
            )
    
    async def _process_with_agents(
        self,
        request_type: str,
        request_data: Dict[str, Any],
        user_id: int,
        board_id: Optional[int],
        session: Optional[AsyncSession]
    ) -> Dict[str, Any]:
        """Agent 모드로 처리"""
        try:
            logger.info(f"Processing with agents: {request_type}")
            
            # 1. 컨텍스트 생성
            async with context_manager.managed_context(
                user_id=user_id,
                task_type=request_type,
                board_id=board_id,
                complexity=request_data.get('complexity', 2)
            ) as context:
                
                # 2. 요청 타입에 따른 에이전트 체인 구성
                agent_chain = await self._build_agent_chain_for_request(
                    request_type, request_data, context
                )
                
                if not agent_chain:
                    raise ValueError(f"No suitable agent chain for request type: {request_type}")
                
                logger.info(f"Using agent chain: {agent_chain}")
                
                # 3. 에이전트 체인 실행
                coordinated_response = await agent_coordinator.execute_agent_chain(
                    agent_chain=agent_chain,
                    initial_input=request_data,
                    context=context,
                    session=session
                )
                
                # 4. 결과 포맷팅
                result = {
                    'success': coordinated_response.success,
                    'content': coordinated_response.final_content,
                    'metadata': coordinated_response.metadata,
                    'wtu_consumed': coordinated_response.total_wtu_consumed,
                    'execution_time_ms': coordinated_response.total_execution_time_ms,
                    'agents_used': [name for name, _ in coordinated_response.agent_responses],
                    'mode': 'agent'
                }
                
                if not coordinated_response.success:
                    result['error_message'] = "; ".join(coordinated_response.error_messages)
                
                return result
                
        except Exception as e:
            logger.error(f"Agent processing failed: {e}")
            raise
    
    async def _process_with_legacy(
        self,
        request_type: str,
        request_data: Dict[str, Any],
        user_id: int,
        board_id: Optional[int],
        session: Optional[AsyncSession]
    ) -> Dict[str, Any]:
        """Legacy 모드로 처리"""
        try:
            logger.info(f"Processing with legacy system: {request_type}")
            
            # Legacy 어댑터를 통해 기존 시스템 호출
            result = await self.legacy_adapter.process_request(
                request_type=request_type,
                request_data=request_data,
                user_id=user_id,
                board_id=board_id,
                session=session
            )
            
            # 표준 형식으로 포맷팅
            if result:
                result['mode'] = 'legacy'
                return result
            else:
                raise ValueError("Legacy processing returned empty result")
                
        except Exception as e:
            logger.error(f"Legacy processing failed: {e}")
            raise
    
    async def _build_agent_chain_for_request(
        self,
        request_type: str,
        request_data: Dict[str, Any],
        context: AgentContext
    ) -> List[str]:
        """요청 타입에 따른 에이전트 체인 구성"""
        try:
            complexity = request_data.get('complexity', context.complexity)
            quality_preference = context.user_model_preferences.quality_preference
            
            # 요청 타입별 기본 체인
            base_chains = {
                'board_analysis': ['content_analysis', 'summary_generation'],
                'clipper': ['content_analysis', 'summary_generation'],
                'summary': ['summary_generation'],
                'content_analysis': ['content_analysis'],
                'validation': ['validator']
            }
            
            agent_chain = base_chains.get(request_type, ['content_analysis'])
            
            # 복잡도와 품질 선호도에 따른 체인 조정
            if complexity >= 3 or quality_preference == "quality":
                # 고품질 모드: 검증 에이전트 추가
                if 'validator' not in agent_chain:
                    agent_chain.append('validator')
            
            if complexity >= 4:
                # 매우 복잡한 작업: 추가 분석 단계
                if request_type in ['board_analysis', 'clipper']:
                    # 현재는 기본 체인 유지 (필요시 확장)
                    pass
            
            # 사용 가능한 에이전트만 필터링
            available_agents = agent_coordinator.get_available_agents()
            filtered_chain = [agent for agent in agent_chain if agent in available_agents]
            
            logger.info(f"Agent chain for {request_type}: {filtered_chain}")
            return filtered_chain
            
        except Exception as e:
            logger.error(f"Failed to build agent chain: {e}")
            return ['content_analysis']  # 기본 폴백
    
    def _update_success_stats(self, mode: str, success: bool):
        """성공률 통계 업데이트"""
        try:
            if mode in self.routing_stats['success_rate_by_mode']:
                self.routing_stats['success_rate_by_mode'][mode]['total'] += 1
                if success:
                    self.routing_stats['success_rate_by_mode'][mode]['success'] += 1
        except Exception as e:
            logger.warning(f"Failed to update success stats: {e}")
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """라우팅 통계 반환"""
        try:
            stats = self.routing_stats.copy()
            
            # 성공률 계산
            for mode, data in stats['success_rate_by_mode'].items():
                if data['total'] > 0:
                    data['success_rate'] = data['success'] / data['total']
                else:
                    data['success_rate'] = 0.0
            
            # 모드별 사용 비율
            total = stats['total_requests']
            if total > 0:
                stats['mode_distribution'] = {
                    'legacy_ratio': stats['legacy_count'] / total,
                    'agent_ratio': stats['agent_count'] / total,
                    'fallback_ratio': stats['fallback_count'] / total
                }
            else:
                stats['mode_distribution'] = {
                    'legacy_ratio': 0.0,
                    'agent_ratio': 0.0,
                    'fallback_ratio': 0.0
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get routing stats: {e}")
            return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """라우터 건강성 확인"""
        try:
            health_status = {
                'router_status': 'healthy',
                'legacy_adapter_status': 'unknown',
                'agent_coordinator_status': 'unknown',
                'available_agents': [],
                'timestamp': datetime.now().isoformat()
            }
            
            # Legacy 어댑터 상태 확인
            try:
                legacy_health = await self.legacy_adapter.health_check()
                health_status['legacy_adapter_status'] = 'healthy' if legacy_health.get('status') == 'ok' else 'unhealthy'
            except Exception as e:
                health_status['legacy_adapter_status'] = f'error: {str(e)}'
            
            # Agent 코디네이터 상태 확인
            try:
                available_agents = agent_coordinator.get_available_agents()
                health_status['available_agents'] = available_agents
                health_status['agent_coordinator_status'] = 'healthy' if available_agents else 'no_agents'
            except Exception as e:
                health_status['agent_coordinator_status'] = f'error: {str(e)}'
            
            # 전체 상태 판정
            if (health_status['legacy_adapter_status'] == 'healthy' or 
                health_status['agent_coordinator_status'] == 'healthy'):
                health_status['overall_status'] = 'healthy'
            else:
                health_status['overall_status'] = 'unhealthy'
                health_status['router_status'] = 'degraded'
            
            return health_status
            
        except Exception as e:
            return {
                'router_status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


# 글로벌 스마트 라우터 인스턴스
smart_router = SmartRouter()