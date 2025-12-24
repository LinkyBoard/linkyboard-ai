"""Summarizer Agent"""

from app.core.llm import (
    LLMMessage,
    LLMTier,
    call_with_fallback,
    get_observe_decorator,
)
from app.domains.topics.agents.base import AgentContext, BaseAgent
from app.domains.topics.orchestration.models import (
    AgentExecutionStatus,
    AgentResult,
)
from app.domains.topics.prompts.summarizer import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)

observe = get_observe_decorator()


class SummarizerAgent(BaseAgent):
    """콘텐츠 요약 에이전트"""

    def __init__(self):
        super().__init__(tier=LLMTier.LIGHT)

    @property
    def name(self) -> str:
        return "summarizer"

    def build_messages(self, context: AgentContext) -> list[LLMMessage]:
        """요약 프롬프트 구성"""
        return [
            LLMMessage(
                role="system",
                content=SYSTEM_PROMPT,
            ),
            LLMMessage(
                role="user",
                content=USER_PROMPT_TEMPLATE.format(content=context.prompt),
            ),
        ]

    @observe()
    async def run_with_fallback(self, context: AgentContext) -> AgentResult:
        """Core LLM을 사용한 요약 실행"""
        messages = self.build_messages(context)

        result = await call_with_fallback(
            tier=self.tier,
            messages=messages,
            session=context.session,
            temperature=0.3,  # 요약은 낮은 온도
        )

        return AgentResult(
            agent=self.name,
            status=AgentExecutionStatus.COMPLETED,
            success=True,
            content=result.content,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            output={
                "summary": result.content,
            },
        )
