"""Orchestration Models 유닛 테스트

Pydantic 모델 검증 및 기본 동작 확인
"""

import pytest
from pydantic import ValidationError

from app.domains.topics.orchestration.models import (
    AgentExecutionStatus,
    AgentResult,
    AgentSpec,
    AgentUsage,
    ExecutionPlan,
    ExecutionResult,
    OrchestrationContext,
    PlanStage,
    RetrievalMode,
    StreamEvent,
    UsageSummary,
)


class TestRetrievalMode:
    """RetrievalMode Enum 테스트"""

    def test_all_values(self):
        """모든 enum 값 존재 확인"""
        assert RetrievalMode.AUTO == "auto"
        assert RetrievalMode.RAG_ONLY == "rag_only"
        assert RetrievalMode.WEB_ONLY == "web_only"
        assert RetrievalMode.BOTH == "both"


class TestAgentExecutionStatus:
    """AgentExecutionStatus Enum 테스트"""

    def test_all_statuses(self):
        """모든 상태 값 존재 확인"""
        assert AgentExecutionStatus.PENDING == "pending"
        assert AgentExecutionStatus.RUNNING == "running"
        assert AgentExecutionStatus.COMPLETED == "completed"
        assert AgentExecutionStatus.FAILED == "failed"
        assert AgentExecutionStatus.SKIPPED == "skipped"


class TestAgentSpec:
    """AgentSpec 모델 테스트"""

    def test_minimal_creation(self):
        """최소 필드로 생성"""
        spec = AgentSpec(agent="test_agent")

        assert spec.agent == "test_agent"
        assert spec.reason is None
        assert spec.options == {}

    def test_full_creation(self):
        """모든 필드 포함 생성"""
        spec = AgentSpec(
            agent="summarizer",
            reason="콘텐츠 요약",
            options={"temperature": 0.7, "max_tokens": 500},
        )

        assert spec.agent == "summarizer"
        assert spec.reason == "콘텐츠 요약"
        assert spec.options["temperature"] == 0.7
        assert spec.options["max_tokens"] == 500

    def test_missing_agent_raises_error(self):
        """agent 필드 누락 시 ValidationError"""
        with pytest.raises(ValidationError):
            AgentSpec()


class TestPlanStage:
    """PlanStage 모델 테스트"""

    def test_minimal_creation(self):
        """최소 필드로 생성"""
        stage = PlanStage(index=1)

        assert stage.index == 1
        assert stage.parallel is False
        assert stage.agents == []

    def test_with_agents(self):
        """에이전트 포함 생성"""
        stage = PlanStage(
            index=1,
            parallel=False,
            agents=[
                AgentSpec(agent="summarizer", reason="요약"),
                AgentSpec(agent="writer", reason="작성"),
            ],
        )

        assert stage.index == 1
        assert len(stage.agents) == 2
        assert stage.agents[0].agent == "summarizer"
        assert stage.agents[1].agent == "writer"

    def test_parallel_stage(self):
        """병렬 실행 Stage"""
        stage = PlanStage(
            index=2,
            parallel=True,
            agents=[AgentSpec(agent="agent1"), AgentSpec(agent="agent2")],
        )

        assert stage.parallel is True
        assert len(stage.agents) == 2


class TestExecutionPlan:
    """ExecutionPlan 모델 테스트"""

    def test_minimal_creation(self):
        """최소 필드로 생성"""
        plan = ExecutionPlan(
            plan_id="plan_123",
            request_type="draft",
        )

        assert plan.plan_id == "plan_123"
        assert plan.request_type == "draft"
        assert plan.retrieval_mode == RetrievalMode.AUTO
        assert plan.stages == []
        assert plan.metadata == {}

    def test_full_creation(self):
        """모든 필드 포함 생성"""
        plan = ExecutionPlan(
            plan_id="plan_456",
            request_type="ask",
            retrieval_mode=RetrievalMode.RAG_ONLY,
            stages=[
                PlanStage(
                    index=1,
                    agents=[AgentSpec(agent="summarizer")],
                )
            ],
            metadata={"topic_id": 100, "user_id": 1},
        )

        assert plan.plan_id == "plan_456"
        assert plan.request_type == "ask"
        assert plan.retrieval_mode == RetrievalMode.RAG_ONLY
        assert len(plan.stages) == 1
        assert plan.metadata["topic_id"] == 100

    def test_invalid_request_type(self):
        """request_type이 draft/ask가 아닌 경우 ValidationError"""
        with pytest.raises(ValidationError):
            ExecutionPlan(
                plan_id="plan_123",
                request_type="invalid_type",
            )


class TestAgentUsage:
    """AgentUsage 모델 테스트"""

    def test_default_values(self):
        """기본값 검증"""
        usage = AgentUsage()

        assert usage.model is None
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.wtu == 0

    def test_with_values(self):
        """값 설정 검증"""
        usage = AgentUsage(
            model="gpt-4",
            input_tokens=100,
            output_tokens=50,
            wtu=2,
        )

        assert usage.model == "gpt-4"
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.wtu == 2


class TestUsageSummary:
    """UsageSummary 모델 테스트"""

    def test_default_values(self):
        """기본값 검증"""
        summary = UsageSummary()

        assert summary.total_input_tokens == 0
        assert summary.total_output_tokens == 0
        assert summary.total_wtu == 0
        assert summary.agents == {}

    def test_with_agent_usage(self):
        """에이전트별 사용량 포함"""
        summary = UsageSummary(
            total_input_tokens=600,
            total_output_tokens=350,
            total_wtu=3,
            agents={
                "summarizer": AgentUsage(
                    model="gpt-4o-mini",
                    input_tokens=100,
                    output_tokens=50,
                    wtu=1,
                ),
                "writer": AgentUsage(
                    model="gpt-4o",
                    input_tokens=500,
                    output_tokens=300,
                    wtu=2,
                ),
            },
        )

        assert summary.total_input_tokens == 600
        assert summary.total_output_tokens == 350
        assert summary.total_wtu == 3
        assert len(summary.agents) == 2
        assert summary.agents["summarizer"].input_tokens == 100
        assert summary.agents["writer"].wtu == 2


class TestAgentResult:
    """AgentResult 모델 테스트"""

    def test_minimal_creation(self):
        """최소 필드로 생성"""
        result = AgentResult(
            agent="test_agent",
            status=AgentExecutionStatus.COMPLETED,
            success=True,
        )

        assert result.agent == "test_agent"
        assert result.status == AgentExecutionStatus.COMPLETED
        assert result.success is True
        assert result.skipped is False
        assert result.warning is None
        assert result.content is None
        assert result.output is None
        assert result.error is None
        assert result.model is None
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_full_creation(self):
        """모든 필드 포함 생성"""
        result = AgentResult(
            agent="writer",
            status=AgentExecutionStatus.COMPLETED,
            success=True,
            content="Draft content",
            output={"draft_md": "# Title\n\nBody", "title": "Title"},
            model="gpt-4o",
            input_tokens=500,
            output_tokens=300,
        )

        assert result.agent == "writer"
        assert result.success is True
        assert result.content == "Draft content"
        assert result.output["title"] == "Title"
        assert result.model == "gpt-4o"
        assert result.input_tokens == 500
        assert result.output_tokens == 300

    def test_failed_result(self):
        """실패 결과 생성"""
        result = AgentResult(
            agent="failed_agent",
            status=AgentExecutionStatus.FAILED,
            success=False,
            error="Something went wrong",
        )

        assert result.status == AgentExecutionStatus.FAILED
        assert result.success is False
        assert result.error == "Something went wrong"

    def test_skipped_result(self):
        """스킵 결과 생성"""
        result = AgentResult(
            agent="skipped_agent",
            status=AgentExecutionStatus.SKIPPED,
            success=False,
            skipped=True,
            warning="Agent not registered",
        )

        assert result.status == AgentExecutionStatus.SKIPPED
        assert result.success is False
        assert result.skipped is True
        assert result.warning == "Agent not registered"


class TestExecutionResult:
    """ExecutionResult 모델 테스트"""

    def test_minimal_creation(self):
        """최소 필드로 생성"""
        result = ExecutionResult(plan_id="plan_123")

        assert result.plan_id == "plan_123"
        assert result.results == []
        assert result.usage.total_wtu == 0
        assert result.final_output is None
        assert result.warnings == []

    def test_full_creation(self):
        """모든 필드 포함 생성"""
        result = ExecutionResult(
            plan_id="plan_456",
            results=[
                AgentResult(
                    agent="summarizer",
                    status=AgentExecutionStatus.COMPLETED,
                    success=True,
                    model="gpt-4o-mini",
                    input_tokens=100,
                    output_tokens=50,
                ),
                AgentResult(
                    agent="writer",
                    status=AgentExecutionStatus.COMPLETED,
                    success=True,
                    model="gpt-4o",
                    input_tokens=500,
                    output_tokens=300,
                ),
            ],
            usage=UsageSummary(
                total_input_tokens=600,
                total_output_tokens=350,
                total_wtu=3,
            ),
            final_output={"title": "Test", "draft_md": "# Test\n\nContent"},
            warnings=["Warning 1", "Warning 2"],
        )

        assert result.plan_id == "plan_456"
        assert len(result.results) == 2
        assert result.usage.total_input_tokens == 600
        assert result.final_output["title"] == "Test"
        assert len(result.warnings) == 2


class TestOrchestrationContext:
    """OrchestrationContext 모델 테스트"""

    def test_minimal_creation(self):
        """최소 필드로 생성"""
        context = OrchestrationContext(
            request_id="req_123",
            user_id=1,
        )

        assert context.request_id == "req_123"
        assert context.user_id == 1
        assert context.topic_id is None
        assert context.prompt is None
        assert context.selected_contents == []
        assert context.stream is False
        assert context.verbose is False
        assert context.metadata == {}

    def test_full_creation(self):
        """모든 필드 포함 생성"""
        context = OrchestrationContext(
            request_id="req_456",
            user_id=2,
            topic_id=100,
            prompt="Write about Python",
            selected_contents=[
                {"content_id": 1, "title": "Content 1"},
            ],
            stream=True,
            verbose=True,
            metadata={"source": "api"},
        )

        assert context.request_id == "req_456"
        assert context.user_id == 2
        assert context.topic_id == 100
        assert context.prompt == "Write about Python"
        assert len(context.selected_contents) == 1
        assert context.stream is True
        assert context.verbose is True
        assert context.metadata["source"] == "api"


class TestStreamEvent:
    """StreamEvent 모델 테스트"""

    def test_creation(self):
        """StreamEvent 생성"""
        event = StreamEvent(
            event="status",
            data={"stage": 1, "agent": "summarizer"},
        )

        assert event.event == "status"
        assert event.data["stage"] == 1
        assert event.data["agent"] == "summarizer"

    def test_nested_data(self):
        """중첩된 데이터 구조"""
        event = StreamEvent(
            event="plan",
            data={
                "plan_id": "plan_123",
                "stages": [
                    {"index": 1, "agents": ["summarizer"]},
                    {"index": 2, "agents": ["writer"]},
                ],
            },
        )

        assert event.event == "plan"
        assert event.data["plan_id"] == "plan_123"
        assert len(event.data["stages"]) == 2
        assert event.data["stages"][0]["index"] == 1
