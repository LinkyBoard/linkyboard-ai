"""
LangGraph Agent 상태 관리

에이전트 실행 간 데이터 전달 및 상태 관리를 담당합니다.
"""

from typing import Dict, Any, List, Optional, TypedDict, Annotated
from datetime import datetime
import operator

from app.agents.schemas import AgentContext, UserModelPreferences


class AgentState(TypedDict):
    """에이전트 실행 상태"""
    
    # 기본 컨텍스트 정보
    user_id: int
    board_id: Optional[int]
    session_id: str
    
    # 입력 데이터
    input_data: Dict[str, Any]
    
    # 처리 결과들 (각 노드의 출력을 누적)
    results: Annotated[Dict[str, Any], operator.add]
    
    # 메시지 히스토리
    messages: Annotated[List[Dict[str, Any]], operator.add]
    
    # 에러 정보
    errors: Annotated[List[str], operator.add]
    
    # 메타데이터
    metadata: Dict[str, Any]
    
    # 모델 선호도
    user_preferences: UserModelPreferences
    
    # 실행 통계
    total_tokens_used: int
    total_wtu_consumed: float
    total_cost_usd: float
    execution_start_time: datetime
    
    # 노드 실행 상태
    completed_nodes: Annotated[List[str], operator.add]
    current_node: Optional[str]
    
    # 조건부 라우팅을 위한 플래그
    should_validate: bool
    should_classify: bool
    should_extract_tags: bool
    complexity_level: int
    
    # 최종 출력
    final_output: Optional[Dict[str, Any]]
    success: bool


def create_initial_state(
    user_id: int,
    input_data: Dict[str, Any],
    context: AgentContext,
    session_id: str
) -> AgentState:
    """초기 에이전트 상태 생성"""
    return AgentState(
        user_id=user_id,
        board_id=context.board_id,
        session_id=session_id,
        input_data=input_data,
        results={},
        messages=[],
        errors=[],
        metadata={
            "created_at": datetime.now().isoformat(),
            "context": context.dict()
        },
        user_preferences=context.user_model_preferences,
        total_tokens_used=0,
        total_wtu_consumed=0.0,
        total_cost_usd=0.0,
        execution_start_time=datetime.now(),
        completed_nodes=[],
        current_node=None,
        should_validate=context.complexity >= 3,
        should_classify=True,
        should_extract_tags=True,
        complexity_level=context.complexity,
        final_output=None,
        success=False
    )


def update_state_with_node_result(
    state: AgentState,
    node_name: str,
    result: Dict[str, Any],
    tokens_used: int = 0,
    wtu_consumed: float = 0.0,
    cost_usd: float = 0.0
) -> Dict[str, Any]:
    """노드 실행 결과로 상태 업데이트"""
    return {
        "results": {node_name: result},
        "completed_nodes": [node_name],
        "current_node": node_name,
        "total_tokens_used": state["total_tokens_used"] + tokens_used,
        "total_wtu_consumed": state["total_wtu_consumed"] + wtu_consumed,
        "total_cost_usd": state["total_cost_usd"] + cost_usd,
        "messages": [
            {
                "node": node_name,
                "timestamp": datetime.now().isoformat(),
                "result": result,
                "tokens_used": tokens_used,
                "wtu_consumed": wtu_consumed
            }
        ]
    }


def add_error_to_state(state: AgentState, node_name: str, error_message: str) -> Dict[str, Any]:
    """에러 정보를 상태에 추가"""
    return {
        "errors": [f"{node_name}: {error_message}"],
        "current_node": node_name,
        "messages": [
            {
                "node": node_name,
                "timestamp": datetime.now().isoformat(),
                "error": error_message,
                "success": False
            }
        ]
    }


def finalize_state(state: AgentState, final_output: Dict[str, Any], success: bool = True) -> Dict[str, Any]:
    """최종 상태로 업데이트"""
    execution_time = (datetime.now() - state["execution_start_time"]).total_seconds()
    
    final_output_with_stats = {
        **final_output,
        "execution_stats": {
            "total_tokens_used": state["total_tokens_used"],
            "total_wtu_consumed": state["total_wtu_consumed"],
            "total_cost_usd": state["total_cost_usd"],
            "execution_time_seconds": execution_time,
            "completed_nodes": state["completed_nodes"],
            "errors": state["errors"]
        }
    }
    
    return {
        "final_output": final_output_with_stats,
        "success": success and len(state["errors"]) == 0,
        "current_node": "completed"
    }