"""Base Agent 추상 클래스

모든 에이전트는 이 인터페이스를 구현해야 합니다.
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from app.core.llm import LLMMessage, LLMTier


class AgentContext(BaseModel):
    """에이전트 실행 컨텍스트"""

    request_id: str
    user_id: int
    prompt: str
    additional_data: dict[str, Any] = {}


class AgentResult(BaseModel):
    """에이전트 실행 결과"""

    agent_name: str
    success: bool
    content: str
    model_used: str
    input_tokens: int
    output_tokens: int
    error: str | None = None


class BaseAgent(ABC):
    """모든 에이전트의 기본 클래스"""

    def __init__(self, tier: LLMTier):
        self.tier = tier

    @property
    @abstractmethod
    def name(self) -> str:
        """에이전트 이름"""
        pass

    @abstractmethod
    def build_messages(self, context: AgentContext) -> list[LLMMessage]:
        """컨텍스트로부터 LLM 메시지 구성"""
        pass

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResult:
        """에이전트 실행 (Core LLM 사용)"""
        pass
