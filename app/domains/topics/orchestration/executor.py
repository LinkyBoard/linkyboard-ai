"""오케스트레이션 Executor 스켈레톤

Phase 1.0에서는 Summarizer → (Researcher) → Writer 순차 실행만 필요하지만,
향후 Stage 병렬 실행을 고려하여 이벤트 훅과 Stage 루프 뼈대를 미리 정의한다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm.wtu import calculate_wtu_from_tokens
from app.core.logging import get_logger
from app.domains.topics.orchestration.models import (
    AgentContext,
    AgentExecutionStatus,
    AgentResult,
    AgentSpec,
    AgentUsage,
    EventCallback,
    ExecutionPlan,
    ExecutionResult,
    OrchestrationContext,
    PlanStage,
    StreamEvent,
    UsageSummary,
)

# Import BaseAgent only for type checking to avoid circular import
if TYPE_CHECKING:
    from app.domains.topics.agents.base import BaseAgent

logger = get_logger(__name__)


class OrchestrationExecutor:
    """ExecutionPlan을 실제로 수행하는 Executor 기본 구현"""

    def __init__(
        self,
        agents: dict[str, BaseAgent] | None = None,
        session: AsyncSession | None = None,
    ):
        self._agents = agents or {}
        self._session = session

    def register_agent(self, agent: BaseAgent) -> None:
        """동적으로 에이전트를 등록할 수 있도록 허용"""
        logger.info(
            "Registering agent for orchestration", extra={"agent": agent.name}
        )
        self._agents[agent.name] = agent

    async def execute(
        self,
        plan: ExecutionPlan,
        context: OrchestrationContext,
        event_callback: EventCallback | None = None,
    ) -> ExecutionResult:
        """ExecutionPlan 기반으로 순차 실행

        각 Stage의 결과를 누적하여 다음 Stage에 전달합니다.
        """
        logger.info(
            "Starting orchestration execution",
            extra={"plan_id": plan.plan_id, "stages": len(plan.stages)},
        )
        results: list[AgentResult] = []
        accumulated_outputs: dict[str, Any] = {}

        for stage in plan.stages:
            await self._emit_stage_event(stage, event_callback)
            stage_results = await self._run_stage(
                stage, context, accumulated_outputs, event_callback
            )
            results.extend(stage_results)

            # 각 Stage 결과를 누적
            for result in stage_results:
                if result.output:
                    accumulated_outputs[result.agent] = result.output

        warnings = [
            result.warning for result in results if result.warning is not None
        ]

        # WriterAgent의 output을 final_output으로 설정
        # draft API 응답에 title과 draft_md를 제공하기 위함
        writer_result = next((r for r in results if r.agent == "writer"), None)
        final_output = (
            writer_result.output
            if writer_result and writer_result.output
            else {}
        )

        # Usage/WTU 계산
        usage = await self._calculate_usage(results)

        logger.info(
            "Orchestration execution finished",
            extra={
                "plan_id": plan.plan_id,
                "final_output_keys": list(final_output.keys()),
                "total_wtu": usage.total_wtu,
            },
        )

        return ExecutionResult(
            plan_id=plan.plan_id,
            results=results,
            warnings=[w for w in warnings if w],
            usage=usage,
            final_output=final_output,
        )

    async def _run_stage(
        self,
        stage: PlanStage,
        context: OrchestrationContext,
        accumulated_outputs: dict[str, Any],
        event_callback: EventCallback | None = None,
    ) -> list[AgentResult]:
        """Stage 내 에이전트 실행 (현재는 순차 처리만 지원)"""
        stage_results: list[AgentResult] = []

        for agent_spec in stage.agents:
            agent = self._agents.get(agent_spec.agent)
            if agent is None:
                logger.warning(
                    "Agent not registered, skipping execution",
                    extra={"agent": agent_spec.agent},
                )
                stage_results.append(self._build_skipped_result(agent_spec))
                continue

            await self._emit_event(
                "agent_start",
                {"agent": agent_spec.agent, "stage": stage.index},
                event_callback,
            )

            # 이전 에이전트 결과를 컨텍스트에 포함
            agent_context = AgentContext(
                request_id=context.request_id,
                user_id=context.user_id,
                prompt=context.prompt or "",
                session=self._session,
                additional_data={
                    "selected_contents": context.selected_contents,
                    "metadata": context.metadata,
                    "previous_outputs": accumulated_outputs,
                },
            )

            result = await agent.run(agent_context)
            stage_results.append(result)

            await self._emit_event(
                "agent_done",
                {
                    "agent": agent_spec.agent,
                    "stage": stage.index,
                    "success": result.success,
                    "skipped": result.skipped,
                },
                event_callback,
            )

        return stage_results

    async def _emit_stage_event(
        self,
        stage: PlanStage,
        event_callback: EventCallback | None = None,
    ) -> None:
        """Stage 시작 이벤트 전송"""
        await self._emit_event(
            "status",
            {
                "stage": stage.index,
                "parallel": stage.parallel,
                "agents": [spec.agent for spec in stage.agents],
            },
            event_callback,
        )

    async def _emit_event(
        self,
        event_name: str,
        payload: dict[str, Any],
        event_callback: EventCallback | None,
    ) -> None:
        """SSE 핸들러에 이벤트 전달 (옵션)"""
        if event_callback is None:
            return

        await event_callback(StreamEvent(event=event_name, data=payload))

    async def _calculate_usage(
        self, results: list[AgentResult]
    ) -> UsageSummary:
        """에이전트별 사용량을 집계하여 UsageSummary 생성

        Args:
            results: 모든 에이전트 실행 결과

        Returns:
            UsageSummary: 총 토큰 수, WTU 및 에이전트별 상세 정보
        """
        total_input_tokens = 0
        total_output_tokens = 0
        total_wtu = 0
        agents_usage: dict[str, AgentUsage] = {}

        for result in results:
            if not result.success or result.skipped:
                continue

            # 에이전트별 WTU 계산 (DB 기반)
            if self._session:
                wtu = await calculate_wtu_from_tokens(
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    model=result.model or "claude-4.5-haiku",
                    session=self._session,
                )
            else:
                # Fallback: 세션 없으면 간단 계산
                logger.warning("No session for WTU calc, using simple")
                wtu = (result.input_tokens + result.output_tokens) // 1000
                wtu = max(1, wtu)

            # 합산
            total_input_tokens += result.input_tokens
            total_output_tokens += result.output_tokens
            total_wtu += wtu

            # 에이전트별 사용량 기록
            agents_usage[result.agent] = AgentUsage(
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                wtu=wtu,
            )

        return UsageSummary(
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_wtu=total_wtu,
            agents=agents_usage,
        )

    @staticmethod
    def _build_skipped_result(agent_spec: AgentSpec) -> AgentResult:
        """등록되지 않은 에이전트는 스킵 처리"""
        return AgentResult(
            agent=agent_spec.agent,
            status=AgentExecutionStatus.SKIPPED,
            success=False,
            skipped=True,
            warning="Agent implementation not registered yet.",
            content=None,
        )


__all__ = ["OrchestrationExecutor"]
