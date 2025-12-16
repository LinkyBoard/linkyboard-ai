"""Researcher Agent 스켈레톤
추후 구현
"""

from app.core.llm import LLMMessage, LLMTier
from app.domains.topics.agents.base import AgentContext, BaseAgent
from app.domains.topics.orchestration.models import AgentResult


class ResearcherAgent(BaseAgent):
    """웹 검색 및 임시 콘텐츠 생성을 담당 (스켈레톤)"""

    def __init__(self):
        super().__init__(tier=LLMTier.SEARCH)

    @property
    def name(self) -> str:
        return "researcher"

    def build_messages(self, context: AgentContext) -> list[LLMMessage]:
        """웹 검색은 LLM 메시지를 직접 사용하지 않으므로 placeholder"""
        return [
            LLMMessage(
                role="system",
                content="You gather the latest information from the web.",
            ),
            LLMMessage(
                role="user",
                content=context.prompt,
            ),
        ]

    async def run_with_fallback(self, context: AgentContext) -> AgentResult:
        """실제 구현은 이후 단계에서 작성"""
        return self._build_skipped_result(
            warning="ResearcherAgent is not implemented yet.",
        )
