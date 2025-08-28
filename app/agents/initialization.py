"""
Agent System Initialization - 에이전트 시스템 초기화

시스템 시작시 모든 에이전트를 등록하고 초기화합니다.
"""

import asyncio
from typing import Dict, Any
from app.core.logging import get_logger

logger = get_logger(__name__)


class AgentSystemInitializer:
    """에이전트 시스템 초기화기"""
    
    def __init__(self):
        self.initialized = False
        self.initialization_status = {}
        
    async def initialize_agent_system(self) -> Dict[str, Any]:
        """에이전트 시스템 전체 초기화"""
        try:
            logger.info("Starting agent system initialization...")
            
            initialization_results = {
                'overall_success': True,
                'components': {},
                'error_messages': []
            }
            
            # 1. 코어 컴포넌트 초기화
            core_result = await self._initialize_core_components()
            initialization_results['components']['core'] = core_result
            if not core_result['success']:
                initialization_results['overall_success'] = False
                initialization_results['error_messages'].extend(core_result.get('errors', []))
            
            # 2. 에이전트들 등록
            agents_result = await self._register_agents()
            initialization_results['components']['agents'] = agents_result
            if not agents_result['success']:
                initialization_results['overall_success'] = False
                initialization_results['error_messages'].extend(agents_result.get('errors', []))
            
            # 3. 라우팅 시스템 초기화
            routing_result = await self._initialize_routing_system()
            initialization_results['components']['routing'] = routing_result
            if not routing_result['success']:
                initialization_results['overall_success'] = False
                initialization_results['error_messages'].extend(routing_result.get('errors', []))
            
            # 4. 레퍼런스 시스템 초기화 (선택적)
            try:
                reference_result = await self._initialize_reference_system()
                initialization_results['components']['reference'] = reference_result
                if not reference_result['success']:
                    logger.warning("Reference system initialization failed, but continuing...")
                    initialization_results['error_messages'].extend(reference_result.get('errors', []))
            except Exception as e:
                logger.warning(f"Reference system initialization skipped: {e}")
                initialization_results['components']['reference'] = {
                    'success': False, 
                    'skipped': True, 
                    'error': str(e)
                }
            
            # 5. 초기화 완료 상태 설정
            self.initialized = initialization_results['overall_success']
            self.initialization_status = initialization_results
            
            if self.initialized:
                logger.info("Agent system initialization completed successfully")
            else:
                logger.warning("Agent system initialization completed with some failures")
                
            return initialization_results
            
        except Exception as e:
            logger.error(f"Agent system initialization failed: {e}")
            return {
                'overall_success': False,
                'error': str(e),
                'components': {}
            }
    
    async def _initialize_core_components(self) -> Dict[str, Any]:
        """코어 컴포넌트들 초기화"""
        try:
            from .core.coordinator import agent_coordinator
            from .core.context_manager import context_manager
            from .mode_selector import mode_selector_service
            
            # 각 컴포넌트 기본 상태 확인
            coordinator_status = len(agent_coordinator.registered_agents) >= 0  # 빈 상태도 정상
            context_manager_status = hasattr(context_manager, 'active_contexts')
            mode_selector_status = hasattr(mode_selector_service, 'select_processing_mode')
            
            success = all([coordinator_status, context_manager_status, mode_selector_status])
            
            return {
                'success': success,
                'details': {
                    'agent_coordinator': coordinator_status,
                    'context_manager': context_manager_status, 
                    'mode_selector': mode_selector_status
                }
            }
            
        except ImportError as e:
            return {
                'success': False,
                'error': f'Import error: {str(e)}',
                'errors': [f'Core component import failed: {str(e)}']
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'errors': [f'Core component initialization failed: {str(e)}']
            }
    
    async def _register_agents(self) -> Dict[str, Any]:
        """에이전트들 등록"""
        registered_agents = []
        errors = []
        
        try:
            from .core.coordinator import agent_coordinator
            
            # Content Analysis Agent 등록
            try:
                from .specialized.content_agent import ContentAnalysisAgent
                content_agent = ContentAnalysisAgent()
                agent_coordinator.register_agent(content_agent)
                registered_agents.append('ContentAnalysisAgent')
                logger.info("ContentAnalysisAgent registered successfully")
            except Exception as e:
                error_msg = f"ContentAnalysisAgent registration failed: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
            
            # Summary Generation Agent 등록 (기본 구현)
            try:
                from .specialized.summary_agent import SummaryGenerationAgent
                summary_agent = SummaryGenerationAgent()
                agent_coordinator.register_agent(summary_agent)
                registered_agents.append('SummaryGenerationAgent')
                logger.info("SummaryGenerationAgent registered successfully")
            except Exception as e:
                error_msg = f"SummaryGenerationAgent registration failed: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
            
            # Validator Agent 등록 (기본 구현)
            try:
                from .specialized.validator_agent import ValidatorAgent
                validator_agent = ValidatorAgent()
                agent_coordinator.register_agent(validator_agent)
                registered_agents.append('ValidatorAgent')
                logger.info("ValidatorAgent registered successfully")
            except Exception as e:
                error_msg = f"ValidatorAgent registration failed: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
            
            success = len(registered_agents) > 0  # 최소 하나는 등록되어야 성공
            
            return {
                'success': success,
                'registered_agents': registered_agents,
                'total_registered': len(registered_agents),
                'errors': errors
            }
            
        except ImportError as e:
            return {
                'success': False,
                'error': f'Agent import error: {str(e)}',
                'errors': [f'Agent registration failed: {str(e)}'],
                'registered_agents': []
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'errors': [f'Agent registration failed: {str(e)}'],
                'registered_agents': registered_agents
            }
    
    async def _initialize_routing_system(self) -> Dict[str, Any]:
        """라우팅 시스템 초기화"""
        try:
            from .routing.smart_router import smart_router
            from .routing.legacy_adapter import legacy_adapter
            
            # 라우터 상태 확인
            router_health = await smart_router.health_check()
            legacy_health = await legacy_adapter.health_check()
            
            router_ok = router_health.get('router_status') in ['healthy', 'degraded']
            legacy_ok = legacy_health.get('status') == 'ok'
            
            success = router_ok and legacy_ok
            
            return {
                'success': success,
                'details': {
                    'smart_router': router_ok,
                    'legacy_adapter': legacy_ok,
                    'router_health': router_health,
                    'legacy_health': legacy_health
                }
            }
            
        except ImportError as e:
            return {
                'success': False,
                'error': f'Routing import error: {str(e)}',
                'errors': [f'Routing system initialization failed: {str(e)}']
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'errors': [f'Routing system initialization failed: {str(e)}']
            }
    
    async def _initialize_reference_system(self) -> Dict[str, Any]:
        """레퍼런스 시스템 초기화"""
        try:
            from .reference.reference_manager import reference_manager
            from .reference import get_quality_validator
            
            # 레퍼런스 매니저 상태 확인
            manager_ok = hasattr(reference_manager, 'add_reference_material')
            
            # 품질 검증기 초기화
            quality_validator = get_quality_validator()
            validator_ok = hasattr(quality_validator, 'validate_against_references')
            
            success = manager_ok and validator_ok
            
            return {
                'success': success,
                'details': {
                    'reference_manager': manager_ok,
                    'quality_validator': validator_ok
                }
            }
            
        except ImportError as e:
            return {
                'success': False,
                'error': f'Reference import error: {str(e)}',
                'errors': [f'Reference system initialization failed: {str(e)}']
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'errors': [f'Reference system initialization failed: {str(e)}']
            }
    
    def is_initialized(self) -> bool:
        """초기화 완료 여부 확인"""
        return self.initialized
    
    def get_initialization_status(self) -> Dict[str, Any]:
        """초기화 상태 반환"""
        return self.initialization_status


# 글로벌 초기화 인스턴스
system_initializer = AgentSystemInitializer()


async def initialize_agents():
    """에이전트 시스템 초기화 (외부 호출용)"""
    return await system_initializer.initialize_agent_system()


def is_agent_system_ready() -> bool:
    """에이전트 시스템 준비 완료 여부"""
    return system_initializer.is_initialized()


def get_system_status() -> Dict[str, Any]:
    """시스템 상태 조회"""
    return system_initializer.get_initialization_status()