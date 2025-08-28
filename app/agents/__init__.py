"""
Agent 시스템 모듈

이 모듈은 AI 에이전트 기반 응답 품질 향상 시스템을 제공합니다:
- V1/V2 병행 운영
- 사용자 모드 선택 (Legacy/Agent/Auto)
- WTU 통합 에이전트 시스템
- 레퍼런스 기반 품질 검증
- 스마트 라우팅 시스템

주요 구성요소:
- Mode Selector: 처리 모드 자동 선택
- Agent Coordinator: 다중 에이전트 조정
- Smart Router: V1/V2 지능적 라우팅
- Context Manager: 에이전트 실행 컨텍스트 관리
- Reference System: 레퍼런스 기반 품질 검증

사용 예시:
    from app.agents import initialize_agents, mode_selector_service
    
    # 시스템 초기화
    await initialize_agents()
    
    # 모드 선택
    response = await mode_selector_service.select_processing_mode(request)
"""

from .mode_selector import ProcessingModeService, mode_selector_service
from .initialization import initialize_agents, is_agent_system_ready, get_system_status

# 추가적으로 필요한 경우 import (에러 방지를 위해 try-except)
try:
    from .schemas import ProcessingModeRequest, ProcessingModeResponse
except ImportError:
    ProcessingModeRequest = None
    ProcessingModeResponse = None

__all__ = [
    "ProcessingModeService",
    "mode_selector_service",
    "initialize_agents",
    "is_agent_system_ready", 
    "get_system_status"
]

# 조건부 export
if ProcessingModeRequest and ProcessingModeResponse:
    __all__.extend(["ProcessingModeRequest", "ProcessingModeResponse"])