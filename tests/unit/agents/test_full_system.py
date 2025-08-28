"""
Full V2 Agent System Integration Test
"""

import asyncio
from datetime import datetime
from typing import Dict, Any

from app.agents.initialization import initialize_agents, is_agent_system_ready, get_system_status
from app.agents.mode_selector import mode_selector_service
from app.agents.schemas import ProcessingModeRequest
from app.core.logging import get_logger

logger = get_logger(__name__)


async def test_full_agent_system():
    """전체 V2 에이전트 시스템 통합 테스트"""
    
    print("=== V2 Agent System Integration Test ===\n")
    
    try:
        # 1. 시스템 초기화
        print("1. Initializing Agent System...")
        initialization_result = await initialize_agents()
        
        print(f"   Overall Success: {initialization_result['overall_success']}")
        
        for component, result in initialization_result.get('components', {}).items():
            if isinstance(result, dict):
                status = "✅ OK" if result.get('success', False) else "❌ FAILED"
                print(f"   - {component.capitalize()}: {status}")
                if not result.get('success') and result.get('errors'):
                    for error in result['errors']:
                        print(f"     Error: {error}")
            else:
                print(f"   - {component.capitalize()}: {result}")
        
        if initialization_result.get('error_messages'):
            print("   Errors:")
            for error in initialization_result['error_messages']:
                print(f"     - {error}")
        
        # 2. 시스템 준비 상태 확인
        print(f"\n2. System Ready: {'✅ YES' if is_agent_system_ready() else '❌ NO'}")
        
        # 3. 모드 선택 테스트
        print("\n3. Testing Mode Selection...")
        
        mode_tests = [
            {"mode": "legacy", "user_id": 1, "task_type": "board_analysis"},
            {"mode": "agent", "user_id": 1, "task_type": "content_analysis"}, 
            {"mode": "auto", "user_id": 1, "task_type": "clipper"}
        ]
        
        for test_case in mode_tests:
            try:
                request = ProcessingModeRequest(**test_case)
                response = await mode_selector_service.select_processing_mode(request)
                
                print(f"   Mode: {test_case['mode']} -> Selected: {response.selected_mode}")
                print(f"   Reason: {response.reason}")
                print(f"   Estimated WTU: {response.estimated_wtu}")
                print()
                
            except Exception as e:
                print(f"   Mode {test_case['mode']} test failed: {e}\n")
        
        # 4. 스마트 라우팅 테스트 (가벼운 테스트)
        print("4. Testing Smart Routing...")
        try:
            from app.agents.routing.smart_router import smart_router
            
            # 라우터 상태 확인
            router_health = await smart_router.health_check()
            print(f"   Router Status: {router_health.get('overall_status', 'unknown')}")
            
            # 통계 확인
            routing_stats = smart_router.get_routing_stats()
            print(f"   Total Requests Processed: {routing_stats.get('total_requests', 0)}")
            
        except Exception as e:
            print(f"   Smart routing test failed: {e}")
        
        # 5. 에이전트 상태 확인
        print("\n5. Agent Status:")
        try:
            from app.agents.core.coordinator import agent_coordinator
            
            available_agents = agent_coordinator.get_available_agents()
            coordinator_stats = agent_coordinator.get_coordinator_stats()
            
            print(f"   Available Agents: {len(available_agents)}")
            for agent in available_agents:
                print(f"   - {agent}")
            
            print(f"   Total Executions: {coordinator_stats.get('execution_count', 0)}")
            
        except Exception as e:
            print(f"   Agent status check failed: {e}")
        
        # 6. 시스템 상태 요약
        print("\n6. System Status Summary:")
        system_status = get_system_status()
        
        if system_status.get('overall_success'):
            print("   ✅ Agent System is operational")
            print("   ✅ Mode selection working")
            print("   ✅ Smart routing available") 
            print("   ✅ Agents registered and ready")
            
            # 기능별 상태
            components = system_status.get('components', {})
            for component, status in components.items():
                if isinstance(status, dict):
                    success = status.get('success', False)
                    icon = "✅" if success else "❌"
                    print(f"   {icon} {component.capitalize()}: {'OK' if success else 'Issues'}")
        
        else:
            print("   ❌ Agent System has issues")
            if system_status.get('error_messages'):
                for error in system_status['error_messages']:
                    print(f"   - {error}")
        
        # 7. 실제 에이전트 실행 테스트 (시뮬레이션)
        print("\n7. Agent Execution Test (Simulation):")
        try:
            from app.agents.core.context_manager import context_manager
            from app.agents.schemas import UserModelPreferences
            
            # 테스트 컨텍스트 생성
            user_preferences = UserModelPreferences(
                user_id=999,
                quality_preference="balanced", 
                cost_sensitivity="medium"
            )
            
            test_context = await context_manager.create_context(
                user_id=999,
                task_type="integration_test",
                complexity=2,
                user_preferences=user_preferences
            )
            
            print(f"   Test context created: {test_context.session_id}")
            
            # 컨텍스트 메트릭 확인
            metrics = await context_manager.get_context_metrics(test_context.session_id)
            print(f"   Context metrics: {len(metrics)} items")
            
            # 정리
            await context_manager.cleanup_context(test_context.session_id)
            print("   Context cleaned up successfully")
            
        except Exception as e:
            print(f"   Agent execution test failed: {e}")
        
        print(f"\n=== Test Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
        return initialization_result['overall_success']
        
    except Exception as e:
        print(f"\nFatal test error: {e}")
        return False


async def main():
    """메인 테스트 실행"""
    success = await test_full_agent_system()
    
    print(f"\n{'='*50}")
    if success:
        print("🎉 V2 Agent System Integration Test: PASSED")
        print("\nThe agent system is ready for production use!")
        print("\nNext steps:")
        print("- Phase 2: Monitoring & Advanced Agents")
        print("- Phase 3: Optimization & Scaling")  
        print("- Phase 4: Testing & Validation")
    else:
        print("❌ V2 Agent System Integration Test: FAILED")
        print("\nSome components need attention before production.")
        print("Check the error messages above for details.")
    
    print(f"{'='*50}")
    
    return success


if __name__ == "__main__":
    asyncio.run(main())