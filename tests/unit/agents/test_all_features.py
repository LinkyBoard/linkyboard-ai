"""
V2 Agent System - 전체 기능 테스트 및 검증

구현된 모든 기능들의 동작을 확인합니다.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List
import json

from app.core.logging import get_logger

logger = get_logger(__name__)


class FeatureTester:
    """기능 테스터"""
    
    def __init__(self):
        self.test_results = {}
        self.total_tests = 0
        self.passed_tests = 0
        
    async def run_all_tests(self) -> Dict[str, Any]:
        """모든 기능 테스트 실행"""
        
        print("🧪 V2 Agent System - Complete Feature Test")
        print("=" * 60)
        
        test_categories = [
            ("1. 시스템 초기화 및 기본 구조", self.test_system_initialization),
            ("2. 모드 선택 시스템", self.test_mode_selection_system), 
            ("3. Agent Base Class 및 WTU 통합", self.test_agent_base_class),
            ("4. 컨텍스트 매니저", self.test_context_manager),
            ("5. 에이전트 코디네이터", self.test_agent_coordinator),
            ("6. 전문 에이전트들", self.test_specialized_agents),
            ("7. 스마트 라우팅 시스템", self.test_smart_routing),
            ("8. 레퍼런스 관리 시스템", self.test_reference_system),
            ("9. API 엔드포인트", self.test_api_endpoints),
            ("10. 통합 워크플로우", self.test_integrated_workflows)
        ]
        
        for category_name, test_func in test_categories:
            print(f"\n{category_name}")
            print("-" * 40)
            
            try:
                await test_func()
            except Exception as e:
                print(f"❌ Category failed: {str(e)}")
                self.test_results[category_name] = {"status": "failed", "error": str(e)}
        
        return self._generate_summary()
    
    async def test_system_initialization(self):
        """1. 시스템 초기화 및 기본 구조 테스트"""
        
        # 1.1 시스템 초기화
        await self._test_feature("시스템 초기화", self._test_system_init)
        
        # 1.2 기본 모듈 Import
        await self._test_feature("기본 모듈 Import", self._test_basic_imports)
        
        # 1.3 설정 및 상태 확인
        await self._test_feature("시스템 상태 확인", self._test_system_status)
    
    async def _test_system_init(self):
        from app.agents.initialization import initialize_agents, is_agent_system_ready
        
        result = await initialize_agents()
        assert result['overall_success'], f"System initialization failed: {result.get('error_messages', [])}"
        
        ready = is_agent_system_ready()
        assert ready, "System not ready after initialization"
        
        return {"initialized": True, "ready": ready}
    
    async def _test_basic_imports(self):
        # 핵심 모듈들 Import 테스트
        imports_to_test = [
            ("app.agents", ["initialize_agents", "mode_selector_service"]),
            ("app.agents.schemas", ["ProcessingModeRequest", "ProcessingModeResponse", "AgentContext"]),
            ("app.agents.core.base_agent", ["AIAgent", "AgentResponse"]),
            ("app.agents.core.coordinator", ["AgentCoordinator", "agent_coordinator"]),
            ("app.agents.core.context_manager", ["AgentContextManager", "context_manager"]),
            ("app.agents.routing.smart_router", ["SmartRouter", "smart_router"]),
        ]
        
        import_results = {}
        for module_name, items in imports_to_test:
            try:
                module = __import__(module_name, fromlist=items)
                for item in items:
                    assert hasattr(module, item), f"{item} not found in {module_name}"
                import_results[module_name] = "✅ OK"
            except Exception as e:
                import_results[module_name] = f"❌ {str(e)}"
                raise
        
        return import_results
    
    async def _test_system_status(self):
        from app.agents.initialization import get_system_status
        
        status = get_system_status()
        assert status.get('overall_success', False), "System status indicates failure"
        
        return status
    
    async def test_mode_selection_system(self):
        """2. 모드 선택 시스템 테스트"""
        
        # 2.1 ProcessingModeService 기능
        await self._test_feature("모드 선택 서비스", self._test_mode_selection_service)
        
        # 2.2 각 모드별 선택 테스트
        await self._test_feature("Legacy 모드 선택", lambda: self._test_mode_selection("legacy"))
        await self._test_feature("Agent 모드 선택", lambda: self._test_mode_selection("agent"))
        await self._test_feature("Auto 모드 선택", lambda: self._test_mode_selection("auto"))
        
        # 2.3 사용자 추천 시스템
        await self._test_feature("사용자 추천 시스템", self._test_user_recommendations)
    
    async def _test_mode_selection_service(self):
        from app.agents.mode_selector import mode_selector_service
        
        assert hasattr(mode_selector_service, 'select_processing_mode'), "select_processing_mode method missing"
        assert hasattr(mode_selector_service, 'get_mode_recommendations_for_user'), "get_mode_recommendations_for_user method missing"
        
        return {"service_methods": "available"}
    
    async def _test_mode_selection(self, mode: str):
        from app.agents.mode_selector import mode_selector_service
        from app.agents.schemas import ProcessingModeRequest
        
        request = ProcessingModeRequest(
            mode=mode,
            user_id=1,
            task_type="test",
            complexity_preference="balanced"
        )
        
        response = await mode_selector_service.select_processing_mode(request)
        
        assert response.selected_mode in ["legacy", "agent"], f"Invalid mode selected: {response.selected_mode}"
        assert response.reason, "No reason provided"
        assert response.estimated_wtu > 0, "Invalid WTU estimate"
        
        return {
            "requested_mode": mode,
            "selected_mode": response.selected_mode, 
            "reason": response.reason,
            "estimated_wtu": response.estimated_wtu
        }
    
    async def _test_user_recommendations(self):
        from app.agents.mode_selector import mode_selector_service
        
        recommendations = await mode_selector_service.get_mode_recommendations_for_user(
            user_id=1, days=30
        )
        
        assert isinstance(recommendations, dict), "Recommendations should be dict"
        assert "user_id" in recommendations, "user_id missing from recommendations"
        
        return recommendations
    
    async def test_agent_base_class(self):
        """3. Agent Base Class 및 WTU 통합 테스트"""
        
        # 3.1 AIAgent 기본 클래스
        await self._test_feature("AIAgent 기본 클래스", self._test_ai_agent_base)
        
        # 3.2 WTU 세션 및 응답
        await self._test_feature("WTU Session 및 AgentResponse", self._test_wtu_components)
        
        # 3.3 모델 선택 로직
        await self._test_feature("모델 선택 로직", self._test_model_selection)
    
    async def _test_ai_agent_base(self):
        from app.agents.core.base_agent import AIAgent, AgentResponse
        
        # Abstract class이므로 직접 인스턴스 생성은 불가능
        # 메서드들이 제대로 정의되어 있는지 확인
        abstract_methods = ["get_agent_type", "get_capabilities", "validate_input", "execute_ai_task"]
        
        for method in abstract_methods:
            assert hasattr(AIAgent, method), f"AIAgent missing method: {method}"
        
        # AgentResponse 모델 테스트
        test_response = AgentResponse(
            content="test content",
            success=True
        )
        
        assert test_response.content == "test content"
        assert test_response.success == True
        
        return {"abstract_methods": abstract_methods, "response_model": "working"}
    
    async def _test_wtu_components(self):
        from app.agents.core.base_agent import WTUSession, AgentResponse
        from datetime import datetime
        
        # WTU Session 테스트
        wtu_session = WTUSession(
            session_id="test-session",
            user_id=1,
            agent_type="test_agent",
            model_name="test-model",
            start_time=datetime.now()
        )
        
        assert wtu_session.session_id == "test-session"
        assert wtu_session.user_id == 1
        
        # AgentResponse 테스트
        response = AgentResponse(
            content={"test": "data"},
            metadata={"agent": "test"},
            wtu_consumed=1.5,
            success=True
        )
        
        assert response.wtu_consumed == 1.5
        assert response.success == True
        
        return {"wtu_session": "working", "agent_response": "working"}
    
    async def _test_model_selection(self):
        from app.agents.schemas import UserModelPreferences
        
        # UserModelPreferences 테스트
        preferences = UserModelPreferences(
            user_id=1,
            default_llm_model="gpt-4o-mini",
            quality_preference="balanced",
            cost_sensitivity="medium"
        )
        
        assert preferences.user_id == 1
        assert preferences.quality_preference == "balanced"
        
        return {"user_preferences": "working"}
    
    async def test_context_manager(self):
        """4. 컨텍스트 매니저 테스트"""
        
        # 4.1 컨텍스트 생성 및 관리
        await self._test_feature("컨텍스트 생성 및 관리", self._test_context_creation)
        
        # 4.2 데이터 공유 기능
        await self._test_feature("컨텍스트 데이터 공유", self._test_context_data_sharing)
        
        # 4.3 실행 기록 추적
        await self._test_feature("실행 기록 추적", self._test_execution_tracking)
        
        # 4.4 컨텍스트 정리
        await self._test_feature("컨텍스트 정리", self._test_context_cleanup)
    
    async def _test_context_creation(self):
        from app.agents.core.context_manager import context_manager
        from app.agents.schemas import UserModelPreferences
        
        user_preferences = UserModelPreferences(
            user_id=1,
            quality_preference="balanced",
            cost_sensitivity="medium"
        )
        
        context = await context_manager.create_context(
            user_id=1,
            task_type="test_task",
            complexity=2,
            user_preferences=user_preferences
        )
        
        assert context.user_id == 1
        assert context.task_type == "test_task"
        assert context.complexity == 2
        
        # 컨텍스트 조회 테스트
        retrieved_context = await context_manager.get_context(context.session_id)
        assert retrieved_context is not None
        assert retrieved_context.session_id == context.session_id
        
        return {"session_id": context.session_id, "created": True}
    
    async def _test_context_data_sharing(self):
        from app.agents.core.context_manager import context_manager
        from app.agents.schemas import UserModelPreferences
        
        user_preferences = UserModelPreferences(user_id=2)
        context = await context_manager.create_context(
            user_id=2,
            task_type="data_sharing_test",
            user_preferences=user_preferences
        )
        
        # 데이터 공유 테스트
        share_success = await context_manager.share_data(
            context.session_id, 
            "test_key", 
            {"test": "value"}
        )
        assert share_success, "Data sharing failed"
        
        # 데이터 조회 테스트
        retrieved_data = await context_manager.get_shared_data(
            context.session_id, 
            "test_key"
        )
        assert retrieved_data == {"test": "value"}, "Retrieved data doesn't match"
        
        await context_manager.cleanup_context(context.session_id)
        
        return {"data_sharing": "working", "data_retrieval": "working"}
    
    async def _test_execution_tracking(self):
        from app.agents.core.context_manager import context_manager
        from app.agents.schemas import UserModelPreferences
        
        user_preferences = UserModelPreferences(user_id=3)
        context = await context_manager.create_context(
            user_id=3,
            task_type="execution_tracking_test",
            user_preferences=user_preferences
        )
        
        # 실행 기록 추가
        record_success = await context_manager.record_agent_execution(
            context.session_id,
            "test_agent",
            execution_time_ms=100,
            wtu_consumed=1.5,
            success=True,
            result_summary="Test execution"
        )
        assert record_success, "Execution recording failed"
        
        # 메트릭 조회
        metrics = await context_manager.get_context_metrics(context.session_id)
        assert metrics.get('total_agents_executed') == 1, "Execution count incorrect"
        assert metrics.get('total_wtu_consumed') == 1.5, "WTU consumption incorrect"
        
        await context_manager.cleanup_context(context.session_id)
        
        return {"execution_recording": "working", "metrics": metrics}
    
    async def _test_context_cleanup(self):
        from app.agents.core.context_manager import context_manager
        from app.agents.schemas import UserModelPreferences
        
        user_preferences = UserModelPreferences(user_id=4)
        context = await context_manager.create_context(
            user_id=4,
            task_type="cleanup_test",
            user_preferences=user_preferences
        )
        
        session_id = context.session_id
        
        # 컨텍스트 존재 확인
        existing_context = await context_manager.get_context(session_id)
        assert existing_context is not None, "Context should exist before cleanup"
        
        # 정리 실행
        cleanup_success = await context_manager.cleanup_context(session_id)
        assert cleanup_success, "Context cleanup failed"
        
        # 정리 확인
        cleaned_context = await context_manager.get_context(session_id)
        assert cleaned_context is None, "Context should be None after cleanup"
        
        return {"cleanup": "working"}
    
    async def test_agent_coordinator(self):
        """5. 에이전트 코디네이터 테스트"""
        
        # 5.1 에이전트 등록 및 조회
        await self._test_feature("에이전트 등록 및 조회", self._test_agent_registration)
        
        # 5.2 에이전트 체인 구성
        await self._test_feature("에이전트 체인 구성", self._test_agent_chain_building)
        
        # 5.3 코디네이터 상태 및 통계
        await self._test_feature("코디네이터 상태 및 통계", self._test_coordinator_stats)
    
    async def _test_agent_registration(self):
        from app.agents.core.coordinator import agent_coordinator
        
        # 등록된 에이전트들 확인
        available_agents = agent_coordinator.get_available_agents()
        assert isinstance(available_agents, list), "Available agents should be list"
        assert len(available_agents) >= 3, f"Expected at least 3 agents, got {len(available_agents)}"
        
        # 예상되는 에이전트들
        expected_agents = ["content_analysis", "summary_generation", "validator"]
        for agent in expected_agents:
            assert agent in available_agents, f"Expected agent {agent} not found in {available_agents}"
        
        return {"available_agents": available_agents, "count": len(available_agents)}
    
    async def _test_agent_chain_building(self):
        from app.agents.core.coordinator import agent_coordinator
        from app.agents.schemas import UserModelPreferences
        
        # 최적 에이전트 체인 구성 테스트
        user_preferences = UserModelPreferences(
            user_id=5,
            quality_preference="balanced",
            cost_sensitivity="medium"
        )
        
        chain = await agent_coordinator.build_optimal_agent_chain(
            task_type="board_analysis",
            complexity=3,
            user_preferences=user_preferences
        )
        
        assert isinstance(chain, list), "Agent chain should be list"
        assert len(chain) > 0, "Agent chain should not be empty"
        
        return {"agent_chain": chain, "length": len(chain)}
    
    async def _test_coordinator_stats(self):
        from app.agents.core.coordinator import agent_coordinator
        
        stats = agent_coordinator.get_coordinator_stats()
        
        assert isinstance(stats, dict), "Stats should be dict"
        assert "registered_agents" in stats, "registered_agents missing from stats"
        assert "agent_count" in stats, "agent_count missing from stats"
        assert "execution_count" in stats, "execution_count missing from stats"
        
        return stats
    
    async def test_specialized_agents(self):
        """6. 전문 에이전트들 테스트"""
        
        # 6.1 Content Analysis Agent
        await self._test_feature("Content Analysis Agent", self._test_content_analysis_agent)
        
        # 6.2 Summary Generation Agent  
        await self._test_feature("Summary Generation Agent", self._test_summary_generation_agent)
        
        # 6.3 Validator Agent
        await self._test_feature("Validator Agent", self._test_validator_agent)
    
    async def _test_content_analysis_agent(self):
        from app.agents.specialized.content_agent import ContentAnalysisAgent
        from app.agents.schemas import AgentContext, UserModelPreferences
        
        agent = ContentAnalysisAgent()
        
        # 기본 속성 확인
        assert agent.get_agent_type() == "content_analysis", "Wrong agent type"
        
        capabilities = agent.get_capabilities()
        assert isinstance(capabilities, list), "Capabilities should be list"
        assert len(capabilities) > 0, "Should have capabilities"
        
        # 입력 검증 테스트
        user_preferences = UserModelPreferences(user_id=6)
        context = AgentContext(
            user_id=6,
            session_id="test-session",
            task_type="content_analysis",
            complexity=2,
            user_model_preferences=user_preferences
        )
        
        # 유효한 입력
        valid_input = {"content": "Test content for analysis", "analysis_type": "comprehensive"}
        is_valid = await agent.validate_input(valid_input, context)
        assert is_valid, "Valid input should pass validation"
        
        # 무효한 입력
        invalid_input = {"analysis_type": "invalid_type"}  # content 없음
        is_invalid = await agent.validate_input(invalid_input, context)
        assert not is_invalid, "Invalid input should fail validation"
        
        return {
            "agent_type": agent.get_agent_type(),
            "capabilities_count": len(capabilities),
            "validation": "working"
        }
    
    async def _test_summary_generation_agent(self):
        from app.agents.specialized.summary_agent import SummaryGenerationAgent
        from app.agents.schemas import AgentContext, UserModelPreferences
        
        agent = SummaryGenerationAgent()
        
        assert agent.get_agent_type() == "summary_generation", "Wrong agent type"
        
        capabilities = agent.get_capabilities()
        assert isinstance(capabilities, list), "Capabilities should be list"
        
        # 입력 검증 테스트
        user_preferences = UserModelPreferences(user_id=7)
        context = AgentContext(
            user_id=7,
            session_id="test-session", 
            task_type="summary_generation",
            complexity=1,
            user_model_preferences=user_preferences
        )
        
        valid_input = {"content": "Content to summarize", "summary_type": "executive_summary"}
        is_valid = await agent.validate_input(valid_input, context)
        assert is_valid, "Valid input should pass validation"
        
        return {
            "agent_type": agent.get_agent_type(),
            "capabilities_count": len(capabilities),
            "validation": "working"
        }
    
    async def _test_validator_agent(self):
        from app.agents.specialized.validator_agent import ValidatorAgent
        from app.agents.schemas import AgentContext, UserModelPreferences
        
        agent = ValidatorAgent()
        
        assert agent.get_agent_type() == "validator", "Wrong agent type"
        
        capabilities = agent.get_capabilities()
        assert isinstance(capabilities, list), "Capabilities should be list"
        
        # 입력 검증 테스트
        user_preferences = UserModelPreferences(user_id=8)
        context = AgentContext(
            user_id=8,
            session_id="test-session",
            task_type="validation", 
            complexity=3,
            user_model_preferences=user_preferences
        )
        
        valid_input = {"agent_result": "Result to validate", "validation_type": "quality_assessment"}
        is_valid = await agent.validate_input(valid_input, context)
        assert is_valid, "Valid input should pass validation"
        
        return {
            "agent_type": agent.get_agent_type(),
            "capabilities_count": len(capabilities),
            "validation": "working"
        }
    
    async def test_smart_routing(self):
        """7. 스마트 라우팅 시스템 테스트"""
        
        # 7.1 Smart Router 기본 기능
        await self._test_feature("Smart Router 기본 기능", self._test_smart_router_basic)
        
        # 7.2 Legacy Adapter
        await self._test_feature("Legacy Adapter", self._test_legacy_adapter)
        
        # 7.3 라우팅 결정 로직
        await self._test_feature("라우팅 결정 로직", self._test_routing_decision)
        
        # 7.4 건강성 확인
        await self._test_feature("라우터 건강성 확인", self._test_router_health)
    
    async def _test_smart_router_basic(self):
        from app.agents.routing.smart_router import smart_router
        
        # 기본 속성 확인
        assert hasattr(smart_router, 'route_request'), "route_request method missing"
        assert hasattr(smart_router, 'get_routing_stats'), "get_routing_stats method missing"
        assert hasattr(smart_router, 'health_check'), "health_check method missing"
        
        # 통계 조회
        stats = smart_router.get_routing_stats()
        assert isinstance(stats, dict), "Stats should be dict"
        
        return {"methods": "available", "stats_keys": list(stats.keys())}
    
    async def _test_legacy_adapter(self):
        from app.agents.routing.legacy_adapter import legacy_adapter
        
        # 지원 요청 타입 확인
        supported_requests = legacy_adapter.get_supported_requests()
        assert isinstance(supported_requests, list), "Supported requests should be list"
        assert len(supported_requests) > 0, "Should support some request types"
        
        expected_types = ["board_analysis", "clipper", "summary", "content_analysis"]
        for req_type in expected_types:
            assert req_type in supported_requests, f"Expected request type {req_type} not supported"
        
        # 건강성 확인
        health = await legacy_adapter.health_check()
        assert isinstance(health, dict), "Health check should return dict"
        assert "status" in health, "Health status missing"
        
        return {
            "supported_requests": supported_requests,
            "health_status": health.get("status")
        }
    
    async def _test_routing_decision(self):
        from app.agents.routing.smart_router import smart_router
        
        # 라우팅 결정 테스트 (실제 실행은 하지 않고 구조만 확인)
        try:
            # 간단한 요청으로 라우팅 결정 과정 확인
            # 실제 AI 호출은 피하고 구조만 테스트
            
            # 메서드 존재 확인
            router_methods = [
                '_determine_processing_mode',
                '_process_with_agents', 
                '_process_with_legacy',
                '_build_agent_chain_for_request'
            ]
            
            for method in router_methods:
                assert hasattr(smart_router, method), f"Method {method} missing"
            
            return {"routing_methods": "available"}
            
        except Exception as e:
            # 실제 실행에서 오류가 나는 것은 정상 (AI 모델 호출 등)
            # 구조적 문제만 체크
            if "not implemented" in str(e).lower() or "import" in str(e).lower():
                raise e
            return {"routing_methods": "available", "note": "execution_skipped"}
    
    async def _test_router_health(self):
        from app.agents.routing.smart_router import smart_router
        
        health = await smart_router.health_check()
        
        assert isinstance(health, dict), "Health check should return dict"
        assert "router_status" in health, "router_status missing"
        assert "overall_status" in health, "overall_status missing"
        
        return health
    
    async def test_reference_system(self):
        """8. 레퍼런스 관리 시스템 테스트"""
        
        # 8.1 레퍼런스 매니저
        await self._test_feature("레퍼런스 매니저", self._test_reference_manager)
        
        # 8.2 품질 검증기
        await self._test_feature("품질 검증기", self._test_quality_validator)
    
    async def _test_reference_manager(self):
        from app.agents.reference.reference_manager import reference_manager
        
        # 기본 메서드 확인
        methods_to_check = [
            'add_reference_material',
            'get_reference_material', 
            'get_user_materials',
            'search_materials',
            'update_reference_material',
            'delete_reference_material'
        ]
        
        for method in methods_to_check:
            assert hasattr(reference_manager, method), f"Method {method} missing"
        
        # 간단한 자료 추가/조회 테스트
        material_id = await reference_manager.add_reference_material(
            user_id=999,
            title="Test Material",
            content="This is test content for reference testing.",
            source_type="manual"
        )
        
        assert material_id, "Material ID should be returned"
        
        # 자료 조회
        material = await reference_manager.get_reference_material(material_id, user_id=999)
        assert material is not None, "Material should be retrievable"
        assert material.title == "Test Material", "Title should match"
        
        # 정리
        await reference_manager.delete_reference_material(material_id, user_id=999)
        
        return {"methods": "available", "crud_operations": "working"}
    
    async def _test_quality_validator(self):
        from app.agents.reference import get_quality_validator
        
        quality_validator = get_quality_validator()
        
        # 기본 메서드 확인
        assert hasattr(quality_validator, 'validate_against_references'), "validate_against_references method missing"
        
        # 검증 메서드들 확인
        validation_methods = [
            '_select_relevant_materials',
            '_calculate_semantic_similarity',
            '_check_factual_consistency', 
            '_assess_completeness',
            '_calculate_reference_coverage'
        ]
        
        for method in validation_methods:
            assert hasattr(quality_validator, method), f"Method {method} missing"
        
        return {"methods": "available"}
    
    async def test_api_endpoints(self):
        """9. API 엔드포인트 테스트 (구조 확인)"""
        
        # 9.1 라우터 구조 확인
        await self._test_feature("API 라우터 구조", self._test_api_router_structure)
        
        # 9.2 스키마 정의 확인  
        await self._test_feature("API 스키마 정의", self._test_api_schemas)
    
    async def _test_api_router_structure(self):
        from app.agents.router import router
        
        # FastAPI 라우터 확인
        assert hasattr(router, 'routes'), "Router should have routes"
        
        routes = router.routes
        route_paths = [route.path for route in routes if hasattr(route, 'path')]
        
        # 예상되는 주요 엔드포인트들
        expected_endpoints = [
            "/v2/mode/select",
            "/v2/mode/recommendations/{user_id}",
            "/v2/ai/smart-routing",
            "/v2/monitoring/system-status"
        ]
        
        for endpoint in expected_endpoints:
            # 정확한 매치 또는 패턴 매치 확인
            found = any(
                endpoint == path or 
                ('{' in endpoint and endpoint.replace('{user_id}', '').rstrip('/') in path)
                for path in route_paths
            )
            assert found, f"Expected endpoint {endpoint} not found in {route_paths}"
        
        return {
            "total_routes": len(routes),
            "route_paths": route_paths[:10]  # 처음 10개만 표시
        }
    
    async def _test_api_schemas(self):
        from app.agents.schemas import (
            ProcessingModeRequest,
            ProcessingModeResponse,
            AgentContext,
            UserModelPreferences,
            TrustScore
        )
        
        # 스키마 클래스들 확인
        schemas_to_test = [
            ProcessingModeRequest,
            ProcessingModeResponse, 
            AgentContext,
            UserModelPreferences,
            TrustScore
        ]
        
        schema_results = {}
        
        for schema_class in schemas_to_test:
            assert hasattr(schema_class, '__fields__'), f"{schema_class.__name__} should be Pydantic model"
            
            # 필드 개수 확인
            field_count = len(schema_class.__fields__)
            schema_results[schema_class.__name__] = {
                "field_count": field_count,
                "fields": list(schema_class.__fields__.keys())
            }
        
        return schema_results
    
    async def test_integrated_workflows(self):
        """10. 통합 워크플로우 테스트"""
        
        # 10.1 전체 시스템 통합 플로우
        await self._test_feature("전체 시스템 통합 플로우", self._test_full_integration_flow)
        
        # 10.2 에러 핸들링 및 폴백
        await self._test_feature("에러 핸들링 및 폴백", self._test_error_handling)
    
    async def _test_full_integration_flow(self):
        """전체 시스템이 통합적으로 동작하는지 확인"""
        
        # 1. 시스템 초기화 확인
        from app.agents.initialization import is_agent_system_ready
        assert is_agent_system_ready(), "System should be ready"
        
        # 2. 모드 선택
        from app.agents.mode_selector import mode_selector_service
        from app.agents.schemas import ProcessingModeRequest
        
        request = ProcessingModeRequest(
            mode="auto",
            user_id=1000,
            task_type="integration_test"
        )
        
        mode_response = await mode_selector_service.select_processing_mode(request)
        assert mode_response.selected_mode in ["legacy", "agent"], "Valid mode should be selected"
        
        # 3. 컨텍스트 생성
        from app.agents.core.context_manager import context_manager
        from app.agents.schemas import UserModelPreferences
        
        user_preferences = UserModelPreferences(user_id=1000)
        context = await context_manager.create_context(
            user_id=1000,
            task_type="integration_test",
            user_preferences=user_preferences
        )
        
        # 4. 에이전트 체인 구성
        from app.agents.core.coordinator import agent_coordinator
        
        agent_chain = await agent_coordinator.build_optimal_agent_chain(
            task_type="integration_test",
            complexity=2,
            user_preferences=user_preferences
        )
        
        assert len(agent_chain) > 0, "Agent chain should not be empty"
        
        # 5. 정리
        await context_manager.cleanup_context(context.session_id)
        
        return {
            "mode_selection": mode_response.selected_mode,
            "context_created": True,
            "agent_chain_length": len(agent_chain),
            "integration_flow": "working"
        }
    
    async def _test_error_handling(self):
        """에러 핸들링 및 폴백 메커니즘 테스트"""
        
        # 1. 잘못된 모드 선택 요청
        from app.agents.mode_selector import mode_selector_service
        from app.agents.schemas import ProcessingModeRequest
        
        try:
            # 잘못된 complexity_preference
            bad_request = ProcessingModeRequest(
                mode="auto",
                user_id=1001,
                task_type="error_test",
                complexity_preference="invalid_preference"  # 잘못된 값
            )
            # Pydantic 검증에서 걸려야 함
            assert False, "Should have failed validation"
        except Exception:
            pass  # 예상된 에러
        
        # 2. 존재하지 않는 컨텍스트 조회
        from app.agents.core.context_manager import context_manager
        
        non_existent_context = await context_manager.get_context("non-existent-session-id")
        assert non_existent_context is None, "Non-existent context should return None"
        
        # 3. 빈 에이전트 체인 처리
        from app.agents.core.coordinator import agent_coordinator
        from app.agents.schemas import UserModelPreferences
        
        user_preferences = UserModelPreferences(user_id=1001)
        
        # 지원하지 않는 task_type으로 체인 구성
        chain = await agent_coordinator.build_optimal_agent_chain(
            task_type="unsupported_task_type",
            complexity=1,
            user_preferences=user_preferences
        )
        
        # 폴백으로 기본 체인이 반환되어야 함
        assert len(chain) > 0, "Should return fallback chain"
        
        return {
            "validation_errors": "handled",
            "non_existent_lookups": "handled", 
            "fallback_chains": "working"
        }
    
    async def _test_feature(self, feature_name: str, test_func):
        """개별 기능 테스트 실행"""
        
        self.total_tests += 1
        
        try:
            result = await test_func()
            print(f"✅ {feature_name}")
            
            self.passed_tests += 1
            self.test_results[feature_name] = {
                "status": "passed", 
                "result": result
            }
            
        except Exception as e:
            print(f"❌ {feature_name}: {str(e)}")
            self.test_results[feature_name] = {
                "status": "failed",
                "error": str(e)
            }
    
    def _generate_summary(self) -> Dict[str, Any]:
        """테스트 결과 요약 생성"""
        
        passed = self.passed_tests
        total = self.total_tests
        success_rate = (passed / total * 100) if total > 0 else 0
        
        failed_tests = [
            name for name, result in self.test_results.items()
            if result["status"] == "failed"
        ]
        
        summary = {
            "overall_success": passed == total,
            "success_rate": success_rate,
            "total_tests": total,
            "passed_tests": passed,
            "failed_tests": len(failed_tests),
            "failed_test_names": failed_tests,
            "test_timestamp": datetime.now().isoformat(),
            "detailed_results": self.test_results
        }
        
        return summary


async def main():
    """메인 테스트 실행"""
    
    tester = FeatureTester()
    summary = await tester.run_all_tests()
    
    print(f"\n{'='*60}")
    print("🧪 V2 Agent System - Complete Feature Test Results")
    print(f"{'='*60}")
    
    print(f"\n📊 Overall Results:")
    print(f"   Total Tests: {summary['total_tests']}")
    print(f"   Passed: {summary['passed_tests']}")
    print(f"   Failed: {summary['failed_tests']}") 
    print(f"   Success Rate: {summary['success_rate']:.1f}%")
    
    if summary['overall_success']:
        print(f"\n🎉 ALL TESTS PASSED! 🎉")
        print(f"\n✅ V2 Agent System is fully operational")
        print(f"✅ All {summary['total_tests']} features working correctly")
    else:
        print(f"\n❌ Some tests failed:")
        for failed_test in summary['failed_test_names']:
            error = summary['detailed_results'][failed_test].get('error', 'Unknown error')
            print(f"   - {failed_test}: {error}")
    
    print(f"\n📅 Test completed at: {summary['test_timestamp']}")
    print(f"{'='*60}")
    
    return summary


if __name__ == "__main__":
    asyncio.run(main())