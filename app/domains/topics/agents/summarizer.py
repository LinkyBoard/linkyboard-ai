"""Summarizer Agent 구현 예시"""

from app.core.llm import (
    LLMMessage,
    LLMTier,
    call_with_fallback,
    get_observe_decorator,
)
from app.domains.topics.agents.base import AgentContext, AgentResult, BaseAgent
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
    async def run(self, context: AgentContext) -> AgentResult:
        """Core LLM을 사용한 요약 실행"""
        try:
            messages = self.build_messages(context)

            result = await call_with_fallback(
                tier=self.tier, messages=messages, temperature=0.3  # 요약은 낮은 온도
            )

            return AgentResult(
                agent_name=self.name,
                success=True,
                content=result.content,
                model_used=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            )

        except Exception as e:
            return AgentResult(
                agent_name=self.name,
                success=False,
                content="",
                model_used="",
                input_tokens=0,
                output_tokens=0,
                error=str(e),
            )
