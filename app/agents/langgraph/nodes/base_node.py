"""
LangGraph 기본 노드 클래스

모든 LangGraph 노드가 상속받는 기본 클래스입니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.monitoring.langsmith.client import langsmith_manager
from ..state import AgentState, update_state_with_node_result, add_error_to_state

logger = get_logger(__name__)


class BaseNode(ABC):
    """LangGraph 노드 기본 클래스"""
    
    def __init__(self, node_name: str):
        self.node_name = node_name
        self.execution_count = 0
    
    @abstractmethod
    async def process(self, state: AgentState, session: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        노드 처리 로직 구현
        
        Args:
            state: 현재 에이전트 상태
            session: 데이터베이스 세션
            
        Returns:
            상태 업데이트 딕셔너리
        """
        pass
    
    @abstractmethod
    def get_node_type(self) -> str:
        """노드 타입 반환"""
        pass
    
    async def execute(self, state: AgentState, session: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        노드 실행 (공통 로직 + 추적)
        
        Args:
            state: 현재 에이전트 상태
            session: 데이터베이스 세션
            
        Returns:
            업데이트된 상태
        """
        start_time = time.time()
        
        logger.info(f"Executing node: {self.node_name} for user {state['user_id']}")
        
        # LangSmith 추적 시작
        with langsmith_manager.trace_context(
            run_name=f"node.{self.node_name}",
            run_type="tool",
            inputs={
                "node_name": self.node_name,
                "node_type": self.get_node_type(),
                "user_id": state["user_id"],
                "board_id": state["board_id"],
                "session_id": state["session_id"],
                "completed_nodes": state["completed_nodes"],
                "input_keys": list(state["input_data"].keys())
            },
            extra={
                "node_name": self.node_name,
                "user_id": str(state["user_id"]),
                "session_id": state["session_id"]
            }
        ) as run_context:
            
            try:
                # 실제 노드 처리 실행
                result = await self.process(state, session)
                
                execution_time = (time.time() - start_time) * 1000
                
                # 성공 결과 기록
                tokens_used = result.get("tokens_used", 0)
                wtu_consumed = result.get("wtu_consumed", 0.0)
                cost_usd = result.get("cost_usd", 0.0)
                
                # LangSmith에 결과 기록
                if run_context:
                    run_context.end(outputs={
                        "success": True,
                        "result": result,
                        "tokens_used": tokens_used,
                        "wtu_consumed": wtu_consumed,
                        "cost_usd": cost_usd,
                        "execution_time_ms": execution_time
                    })
                
                # 실행 통계 업데이트
                self.execution_count += 1
                
                logger.info(
                    f"Node {self.node_name} completed successfully: "
                    f"tokens={tokens_used}, wtu={wtu_consumed:.3f}, "
                    f"time={execution_time:.1f}ms"
                )
                
                # 상태 업데이트 반환
                return update_state_with_node_result(
                    state=state,
                    node_name=self.node_name,
                    result=result,
                    tokens_used=tokens_used,
                    wtu_consumed=wtu_consumed,
                    cost_usd=cost_usd
                )
                
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                error_message = str(e)
                
                # LangSmith에 에러 기록
                if run_context:
                    run_context.end(
                        error=error_message,
                        outputs={
                            "success": False,
                            "error": error_message,
                            "execution_time_ms": execution_time
                        }
                    )
                
                logger.error(
                    f"Node {self.node_name} failed: {error_message} "
                    f"(time={execution_time:.1f}ms)"
                )
                
                # 에러 상태 반환
                return add_error_to_state(state, self.node_name, error_message)
    
    def get_stats(self) -> Dict[str, Any]:
        """노드 실행 통계 반환"""
        return {
            "node_name": self.node_name,
            "node_type": self.get_node_type(),
            "execution_count": self.execution_count
        }