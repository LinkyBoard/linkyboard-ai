"""Writer Agent"""

import re

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
from app.domains.topics.prompts.writer import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)

observe = get_observe_decorator()


class WriterAgent(BaseAgent):
    """이전 에이전트 결과를 종합해 초안 생성"""

    def __init__(self):
        super().__init__(tier=LLMTier.STANDARD)

    @property
    def name(self) -> str:
        return "writer"

    def build_messages(self, context: AgentContext) -> list[LLMMessage]:
        """초안 작성 프롬프트 구성"""
        # 이전 에이전트 결과를 모두 컨텍스트로 활용
        previous_outputs = context.additional_data.get("previous_outputs", {})

        context_parts = []

        # 이전 에이전트 결과가 있으면 추가
        for agent_name, output in previous_outputs.items():
            if isinstance(output, dict):
                # summary, analysis, search_results 등 다양한 키 처리
                for key, value in output.items():
                    if value and isinstance(value, str):
                        context_parts.append(
                            f"## {agent_name.title()} - {key.title()}\n{value}"
                        )

        # 선택된 콘텐츠 정보
        selected_contents = context.additional_data.get(
            "selected_contents", []
        )
        if selected_contents:
            context_parts.append("\n## 참고 콘텐츠")
            for content in selected_contents:
                title = content.get("title", "")
                summary = content.get("summary", "")
                if title and summary:
                    context_parts.append(f"### {title}\n{summary}\n")

        context_text = (
            "\n\n".join(context_parts)
            if context_parts
            else "No context available."
        )

        return [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=USER_PROMPT_TEMPLATE.format(
                    prompt=context.prompt,
                    context=context_text,
                ),
            ),
        ]

    @observe()
    async def run_with_fallback(self, context: AgentContext) -> AgentResult:
        """Core LLM을 사용한 초안 작성"""
        messages = self.build_messages(context)

        result = await call_with_fallback(
            tier=self.tier,
            messages=messages,
            session=context.session,
            temperature=0.7,
        )

        # 제목 추출 (첫 번째 # 헤더 또는 기본값)
        title = self._extract_title(result.content)

        return AgentResult(
            agent=self.name,
            status=AgentExecutionStatus.COMPLETED,
            success=True,
            content=result.content,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            output={
                "draft_md": result.content,
                "title": title,
            },
        )

    def _extract_title(self, content: str) -> str:
        """마크다운에서 제목 추출"""
        # 첫 번째 # 헤더를 찾음
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()

        # 헤더가 없으면 첫 줄의 일부를 사용
        first_line = content.split("\n")[0].strip()
        return first_line[:50] + "..." if len(first_line) > 50 else first_line
