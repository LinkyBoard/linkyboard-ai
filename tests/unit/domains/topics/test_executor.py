"""Executor 유닛 테스트

OrchestrationExecutor의 핵심 기능 검증:
- 컨텍스트 누적 (previous_outputs)
- Usage/WTU 계산
- final_output 구성
- 에이전트 스킵 처리
"""

import pytest

from app.core.llm import LLMMessage, LLMTier
from app.domains.topics.agents.base import BaseAgent
from app.domains.topics.orchestration.executor import OrchestrationExecutor
from app.domains.topics.orchestration.models import (
    AgentContext,
    AgentExecutionStatus,
    AgentResult,
    AgentSpec,
    ExecutionPlan,
    OrchestrationContext,
    PlanStage,
)


class MockAgent(BaseAgent):
    """테스트용 Mock Agent"""

    def __init__(
        self, name: str, output: dict | None, tokens: tuple[int, int]
    ):
        super().__init__(tier=LLMTier.LIGHT)
        self._name = name
        self._output = output
        self._tokens = tokens  # (input_tokens, output_tokens)

    @property
    def name(self) -> str:
        return self._name

    def build_messages(self, context: AgentContext) -> list[LLMMessage]:
        return []

    async def run_with_fallback(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            agent=self._name,
            status=AgentExecutionStatus.COMPLETED,
            success=True,
            content=f"Mock content from {self._name}",
            output=self._output,
            model="mock-model",
            input_tokens=self._tokens[0],
            output_tokens=self._tokens[1],
        )


class FailingMockAgent(BaseAgent):
    """실패하는 Mock Agent"""

    def __init__(self, name: str, error_message: str):
        super().__init__(tier=LLMTier.LIGHT)
        self._name = name
        self._error_message = error_message

    @property
    def name(self) -> str:
        return self._name

    def build_messages(self, context: AgentContext) -> list[LLMMessage]:
        return []

    async def run_with_fallback(self, context: AgentContext) -> AgentResult:
        raise ValueError(self._error_message)


@pytest.mark.asyncio
async def test_context_accumulation_between_stages():
    """Stage 간 컨텍스트 누적 검증

    Stage 1의 output이 Stage 2의 previous_outputs로 전달되는지 확인
    """
    # Mock summarizer agent
    summarizer = MockAgent(
        name="summarizer",
        output={"summary": "Test summary from stage 1"},
        tokens=(100, 50),
    )

    # Mock writer agent that captures context
    writer_context_capture = {}

    class WriterMockAgent(BaseAgent):
        def __init__(self):
            super().__init__(tier=LLMTier.LIGHT)

        @property
        def name(self) -> str:
            return "writer"

        def build_messages(self, context: AgentContext) -> list[LLMMessage]:
            return []

        async def run_with_fallback(
            self, context: AgentContext
        ) -> AgentResult:
            writer_context_capture[
                "previous_outputs"
            ] = context.additional_data.get("previous_outputs", {})
            return AgentResult(
                agent="writer",
                status=AgentExecutionStatus.COMPLETED,
                success=True,
                output={"draft_md": "# Draft", "title": "Draft"},
                model="mock-model",
                input_tokens=500,
                output_tokens=300,
            )

    executor = OrchestrationExecutor()
    executor.register_agent(summarizer)
    executor.register_agent(WriterMockAgent())

    plan = ExecutionPlan(
        plan_id="test-plan",
        request_type="draft",
        stages=[
            PlanStage(index=1, agents=[AgentSpec(agent="summarizer")]),
            PlanStage(index=2, agents=[AgentSpec(agent="writer")]),
        ],
    )

    context = OrchestrationContext(
        request_id="test-req",
        user_id=1,
        prompt="Test prompt",
    )

    result = await executor.execute(plan, context)

    # Verify writer received summarizer's output
    assert "summarizer" in writer_context_capture["previous_outputs"]
    assert (
        writer_context_capture["previous_outputs"]["summarizer"]["summary"]
        == "Test summary from stage 1"
    )

    # Verify final output is from writer
    assert result.final_output == {"draft_md": "# Draft", "title": "Draft"}


@pytest.mark.asyncio
async def test_usage_calculation():
    """총 토큰 및 WTU 계산 검증"""
    # Setup agents with known token counts
    summarizer = MockAgent(
        name="summarizer", output={"summary": "..."}, tokens=(100, 50)
    )
    writer = MockAgent(
        name="writer", output={"draft": "..."}, tokens=(500, 300)
    )

    executor = OrchestrationExecutor()
    executor.register_agent(summarizer)
    executor.register_agent(writer)

    plan = ExecutionPlan(
        plan_id="test-plan",
        request_type="draft",
        stages=[
            PlanStage(index=1, agents=[AgentSpec(agent="summarizer")]),
            PlanStage(index=2, agents=[AgentSpec(agent="writer")]),
        ],
    )

    context = OrchestrationContext(request_id="test", user_id=1, prompt="Test")

    result = await executor.execute(plan, context)

    # Verify total usage
    assert result.usage.total_input_tokens == 600  # 100 + 500
    assert result.usage.total_output_tokens == 350  # 50 + 300

    # WTU calculation: (600 + 350) / 1000 = 0.95 → 1 (minimum)
    assert result.usage.total_wtu == 2  # Each agent gets minimum 1 WTU

    # Verify per-agent usage
    assert "summarizer" in result.usage.agents
    assert result.usage.agents["summarizer"].input_tokens == 100
    assert result.usage.agents["summarizer"].output_tokens == 50
    assert result.usage.agents["summarizer"].wtu == 1

    assert "writer" in result.usage.agents
    assert result.usage.agents["writer"].input_tokens == 500
    assert result.usage.agents["writer"].output_tokens == 300
    assert result.usage.agents["writer"].wtu == 1


@pytest.mark.asyncio
async def test_wtu_calculation_per_agent():
    """에이전트별 WTU 계산 검증

    - 토큰 < 1000: WTU = 1 (최소값)
    - 토큰 >= 1000: WTU = tokens / 1000
    """
    # Agent with < 1000 tokens → WTU = 1
    small_agent = MockAgent(
        name="small", output={}, tokens=(200, 300)
    )  # 500 total

    # Agent with >= 1000 tokens → WTU = tokens / 1000
    large_agent = MockAgent(
        name="large", output={}, tokens=(700, 800)
    )  # 1500 total

    executor = OrchestrationExecutor()
    executor.register_agent(small_agent)
    executor.register_agent(large_agent)

    plan = ExecutionPlan(
        plan_id="test",
        request_type="draft",
        stages=[
            PlanStage(index=1, agents=[AgentSpec(agent="small")]),
            PlanStage(index=2, agents=[AgentSpec(agent="large")]),
        ],
    )

    context = OrchestrationContext(request_id="test", user_id=1, prompt="Test")

    result = await executor.execute(plan, context)

    # Small agent: 500 tokens → WTU = 1 (minimum)
    assert result.usage.agents["small"].wtu == 1

    # Large agent: 1500 tokens → WTU = 1 (1500 / 1000 = 1.5 → 1 as int)
    assert result.usage.agents["large"].wtu == 1

    # Total WTU
    assert result.usage.total_wtu == 2


@pytest.mark.asyncio
async def test_final_output_construction():
    """final_output 구성 로직 검증

    WriterAgent의 output이 final_output으로 설정되어야 함
    """
    summarizer = MockAgent(
        name="summarizer", output={"summary": "..."}, tokens=(100, 50)
    )
    writer = MockAgent(
        name="writer",
        output={"draft_md": "# My Draft", "title": "My Draft"},
        tokens=(500, 300),
    )

    executor = OrchestrationExecutor()
    executor.register_agent(summarizer)
    executor.register_agent(writer)

    plan = ExecutionPlan(
        plan_id="test",
        request_type="draft",
        stages=[
            PlanStage(index=1, agents=[AgentSpec(agent="summarizer")]),
            PlanStage(index=2, agents=[AgentSpec(agent="writer")]),
        ],
    )

    context = OrchestrationContext(request_id="test", user_id=1, prompt="Test")

    result = await executor.execute(plan, context)

    # final_output should be writer's output
    assert result.final_output == {
        "draft_md": "# My Draft",
        "title": "My Draft",
    }
    assert result.final_output["draft_md"] == "# My Draft"
    assert result.final_output["title"] == "My Draft"


@pytest.mark.asyncio
async def test_final_output_when_writer_fails():
    """WriterAgent 실패 시 final_output 처리

    Writer가 실패하면 final_output은 빈 dict여야 함
    """
    summarizer = MockAgent(
        name="summarizer", output={"summary": "..."}, tokens=(100, 50)
    )
    writer = FailingMockAgent(name="writer", error_message="Writer failed")

    executor = OrchestrationExecutor()
    executor.register_agent(summarizer)
    executor.register_agent(writer)

    plan = ExecutionPlan(
        plan_id="test",
        request_type="draft",
        stages=[
            PlanStage(index=1, agents=[AgentSpec(agent="summarizer")]),
            PlanStage(index=2, agents=[AgentSpec(agent="writer")]),
        ],
    )

    context = OrchestrationContext(request_id="test", user_id=1, prompt="Test")

    result = await executor.execute(plan, context)

    # final_output should be empty when writer fails
    assert result.final_output == {}


@pytest.mark.asyncio
async def test_agent_skipping_when_not_registered():
    """Agent 미등록 시 스킵 처리 검증"""
    executor = OrchestrationExecutor()
    # Don't register any agents

    plan = ExecutionPlan(
        plan_id="test",
        request_type="draft",
        stages=[
            PlanStage(index=1, agents=[AgentSpec(agent="unknown_agent")]),
        ],
    )

    context = OrchestrationContext(request_id="test", user_id=1, prompt="Test")

    result = await executor.execute(plan, context)

    # Should have one skipped result
    assert len(result.results) == 1
    skipped_result = result.results[0]

    assert skipped_result.agent == "unknown_agent"
    assert skipped_result.status == AgentExecutionStatus.SKIPPED
    assert skipped_result.success is False
    assert skipped_result.skipped is True
    assert skipped_result.warning == "Agent implementation not registered yet."

    # Should have warning in execution result
    assert len(result.warnings) == 1
    assert "not registered" in result.warnings[0]


@pytest.mark.asyncio
async def test_accumulated_outputs_with_skipped_agent():
    """스킵된 Agent는 accumulated_outputs에 추가되지 않음"""
    summarizer = MockAgent(
        name="summarizer",
        output={"summary": "Summary"},
        tokens=(100, 50),
    )

    # Writer that checks previous_outputs
    writer_context_capture = {}

    class WriterMockAgent(BaseAgent):
        def __init__(self):
            super().__init__(tier=LLMTier.LIGHT)

        @property
        def name(self) -> str:
            return "writer"

        def build_messages(self, context: AgentContext) -> list[LLMMessage]:
            return []

        async def run_with_fallback(
            self, context: AgentContext
        ) -> AgentResult:
            writer_context_capture[
                "previous_outputs"
            ] = context.additional_data.get("previous_outputs", {})
            return AgentResult(
                agent="writer",
                status=AgentExecutionStatus.COMPLETED,
                success=True,
                output={"draft": "..."},
                model="mock-model",
                input_tokens=500,
                output_tokens=300,
            )

    executor = OrchestrationExecutor()
    executor.register_agent(summarizer)
    # Don't register "skipped_agent"
    executor.register_agent(WriterMockAgent())

    plan = ExecutionPlan(
        plan_id="test",
        request_type="draft",
        stages=[
            PlanStage(index=1, agents=[AgentSpec(agent="summarizer")]),
            PlanStage(index=2, agents=[AgentSpec(agent="skipped_agent")]),
            PlanStage(index=3, agents=[AgentSpec(agent="writer")]),
        ],
    )

    context = OrchestrationContext(request_id="test", user_id=1, prompt="Test")

    await executor.execute(plan, context)

    # Writer should only see summarizer's output, not skipped_agent
    assert "summarizer" in writer_context_capture["previous_outputs"]
    assert "skipped_agent" not in writer_context_capture["previous_outputs"]


@pytest.mark.asyncio
async def test_warnings_aggregation():
    """경고 메시지 집계 검증"""

    # Agent that returns a warning
    class WarningAgent(BaseAgent):
        def __init__(self, name: str, warning: str):
            super().__init__(tier=LLMTier.LIGHT)
            self._name = name
            self._warning = warning

        @property
        def name(self) -> str:
            return self._name

        def build_messages(self, context: AgentContext) -> list[LLMMessage]:
            return []

        async def run_with_fallback(
            self, context: AgentContext
        ) -> AgentResult:
            return AgentResult(
                agent=self._name,
                status=AgentExecutionStatus.COMPLETED,
                success=True,
                warning=self._warning,
                model="mock-model",
                input_tokens=100,
                output_tokens=50,
            )

    agent1 = WarningAgent("agent1", "Warning from agent1")
    agent2 = WarningAgent("agent2", "Warning from agent2")

    executor = OrchestrationExecutor()
    executor.register_agent(agent1)
    executor.register_agent(agent2)

    plan = ExecutionPlan(
        plan_id="test",
        request_type="draft",
        stages=[
            PlanStage(index=1, agents=[AgentSpec(agent="agent1")]),
            PlanStage(index=2, agents=[AgentSpec(agent="agent2")]),
        ],
    )

    context = OrchestrationContext(request_id="test", user_id=1, prompt="Test")

    result = await executor.execute(plan, context)

    # Should have both warnings
    assert len(result.warnings) == 2
    assert "Warning from agent1" in result.warnings
    assert "Warning from agent2" in result.warnings


@pytest.mark.asyncio
async def test_execute_sequential_stages():
    """순차 실행 검증"""
    execution_order = []

    class OrderTrackingAgent(BaseAgent):
        def __init__(self, name: str):
            super().__init__(tier=LLMTier.LIGHT)
            self._name = name

        @property
        def name(self) -> str:
            return self._name

        def build_messages(self, context: AgentContext) -> list[LLMMessage]:
            return []

        async def run_with_fallback(
            self, context: AgentContext
        ) -> AgentResult:
            execution_order.append(self._name)
            return AgentResult(
                agent=self._name,
                status=AgentExecutionStatus.COMPLETED,
                success=True,
                model="mock-model",
                input_tokens=100,
                output_tokens=50,
            )

    agent1 = OrderTrackingAgent("first")
    agent2 = OrderTrackingAgent("second")
    agent3 = OrderTrackingAgent("third")

    executor = OrchestrationExecutor()
    executor.register_agent(agent1)
    executor.register_agent(agent2)
    executor.register_agent(agent3)

    plan = ExecutionPlan(
        plan_id="test",
        request_type="draft",
        stages=[
            PlanStage(index=1, agents=[AgentSpec(agent="first")]),
            PlanStage(index=2, agents=[AgentSpec(agent="second")]),
            PlanStage(index=3, agents=[AgentSpec(agent="third")]),
        ],
    )

    context = OrchestrationContext(request_id="test", user_id=1, prompt="Test")

    await executor.execute(plan, context)

    # Verify execution order
    assert execution_order == ["first", "second", "third"]


@pytest.mark.asyncio
async def test_sse_event_emission():
    """SSE 이벤트 발생 검증"""
    events = []

    async def event_callback(event):
        events.append({"event": event.event, "data": event.data})

    summarizer = MockAgent(name="summarizer", output={}, tokens=(100, 50))
    writer = MockAgent(name="writer", output={}, tokens=(500, 300))

    executor = OrchestrationExecutor()
    executor.register_agent(summarizer)
    executor.register_agent(writer)

    plan = ExecutionPlan(
        plan_id="test",
        request_type="draft",
        stages=[
            PlanStage(index=1, agents=[AgentSpec(agent="summarizer")]),
            PlanStage(index=2, agents=[AgentSpec(agent="writer")]),
        ],
    )

    context = OrchestrationContext(request_id="test", user_id=1, prompt="Test")

    await executor.execute(plan, context, event_callback=event_callback)

    # Verify events were emitted
    event_types = [e["event"] for e in events]

    # Should have status events for each stage
    assert event_types.count("status") >= 2

    # Should have agent_start and agent_done for each agent
    assert event_types.count("agent_start") == 2
    assert event_types.count("agent_done") == 2

    # Verify event structure
    status_events = [e for e in events if e["event"] == "status"]
    assert all("stage" in e["data"] for e in status_events)

    agent_events = [e for e in events if "agent" in e["event"]]
    assert all("agent" in e["data"] for e in agent_events)
