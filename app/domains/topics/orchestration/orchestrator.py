"""Topics 도메인 오케스트레이터 스켈레톤"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.domains.topics.orchestration.executor import OrchestrationExecutor
from app.domains.topics.orchestration.models import (
    AgentSpec,
    EventCallback,
    ExecutionPlan,
    ExecutionResult,
    OrchestrationContext,
    PlanStage,
    RetrievalMode,
    StreamEvent,
)

logger = get_logger(__name__)


class DraftOrchestrationInput(BaseModel):
    """draft 오케스트레이션 입력"""

    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    user_id: int
    topic_id: int
    prompt: str
    selected_contents: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_mode: RetrievalMode = RetrievalMode.AUTO
    stream: bool = False
    verbose: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class TopicsOrchestrator:
    """실행 계획 생성 및 Executor 위임"""

    def __init__(self, executor: OrchestrationExecutor):
        self._executor = executor

    async def run_draft(
        self,
        request: DraftOrchestrationInput,
        event_callback: EventCallback | None = None,
    ) -> ExecutionResult:
        """draft 요청 실행"""
        plan = self._build_draft_plan(request)
        await self._emit_plan_event(plan, event_callback)

        context = OrchestrationContext(
            request_id=request.request_id,
            user_id=request.user_id,
            topic_id=request.topic_id,
            prompt=request.prompt,
            selected_contents=request.selected_contents,
            stream=request.stream,
            verbose=request.verbose,
            metadata=request.metadata,
        )

        return await self._executor.execute(plan, context, event_callback)

    def _build_draft_plan(
        self,
        request: DraftOrchestrationInput,
    ) -> ExecutionPlan:
        """Summarizer -> Writer 기반 고정 플랜
        TODO :
            - plan : 동적 플랜 생성 로직으로 대체
            - 외부 자료 활용, 검색 등 다양한 에이전트 추가
        """
        plan_id = f"plan_{request.request_id}"
        stages = [
            PlanStage(
                index=1,
                parallel=False,
                agents=[
                    AgentSpec(
                        agent="summarizer",
                        reason="선택된 콘텐츠 요약",
                    )
                ],
            ),
            PlanStage(
                index=2,
                parallel=False,
                agents=[
                    AgentSpec(
                        agent="writer",
                        reason="초안 생성",
                    )
                ],
            ),
        ]

        logger.debug(
            "Draft execution plan created",
            extra={"plan_id": plan_id, "stages": len(stages)},
        )

        return ExecutionPlan(
            plan_id=plan_id,
            request_type="draft",
            retrieval_mode=request.retrieval_mode,
            stages=stages,
            metadata={
                "topic_id": request.topic_id,
                "selected_content_count": len(request.selected_contents),
            },
        )

    @staticmethod
    async def _emit_plan_event(
        plan: ExecutionPlan,
        event_callback: EventCallback | None,
    ) -> None:
        """plan 이벤트는 verbose SSE 모드에서만 필요"""
        if event_callback is None:
            return

        await event_callback(
            StreamEvent(
                event="plan",
                data={
                    "plan_id": plan.plan_id,
                    "retrieval_mode": plan.retrieval_mode.value,
                    "stages": [
                        {
                            "index": stage.index,
                            "parallel": stage.parallel,
                            "agents": [
                                {"agent": spec.agent, "reason": spec.reason}
                                for spec in stage.agents
                            ],
                        }
                        for stage in plan.stages
                    ],
                },
            )
        )


__all__ = [
    "DraftOrchestrationInput",
    "TopicsOrchestrator",
]
