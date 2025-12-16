"""Base Agent 추상 클래스

모든 에이전트는 이 인터페이스를 구현해야 합니다.
"""

from abc import ABC, abstractmethod

from app.core.llm import LLMMessage, LLMTier
from app.core.llm.types import AllProvidersFailedError
from app.domains.topics.orchestration.models import (
    AgentContext,
    AgentExecutionStatus,
    AgentResult,
)


class BaseAgent(ABC):
    """모든 에이전트의 기본 클래스"""

    def __init__(self, tier: LLMTier):
        self.tier = tier

    @property
    @abstractmethod
    def name(self) -> str:
        """에이전트 이름"""
        raise NotImplementedError

    @abstractmethod
    def build_messages(self, context: AgentContext) -> list[LLMMessage]:
        """컨텍스트로부터 LLM 메시지 구성"""
        raise NotImplementedError

    async def run(self, context: AgentContext) -> AgentResult:
        """에이전트 실행 (공통 예외 처리 포함)"""
        try:
            return await self.run_with_fallback(context)
        except AllProvidersFailedError as exc:
            return self._build_skipped_result(
                warning="모든 프로바이더가 실패했습니다.",
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            return self._build_failure_result(str(exc))

    @abstractmethod
    async def run_with_fallback(self, context: AgentContext) -> AgentResult:
        """Fallback 전략까지 포함한 실행 (하위 클래스에서 구현)"""
        raise NotImplementedError

    def _build_failure_result(self, error: str) -> AgentResult:
        return AgentResult(
            agent=self.name,
            status=AgentExecutionStatus.FAILED,
            success=False,
            error=error,
        )

    def _build_skipped_result(
        self,
        warning: str,
        error: str | None = None,
    ) -> AgentResult:
        return AgentResult(
            agent=self.name,
            status=AgentExecutionStatus.SKIPPED,
            success=False,
            skipped=True,
            warning=warning,
            error=error,
        )
