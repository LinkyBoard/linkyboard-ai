"""TopicsOrchestrator 유닛 테스트

플랜 빌딩 로직 검증
"""

import pytest

from app.domains.topics.orchestration.executor import OrchestrationExecutor
from app.domains.topics.orchestration.models import RetrievalMode
from app.domains.topics.orchestration.orchestrator import (
    DraftOrchestrationInput,
    TopicsOrchestrator,
)


@pytest.fixture
def orchestrator():
    """테스트용 Orchestrator (빈 Executor)"""
    executor = OrchestrationExecutor()
    return TopicsOrchestrator(executor)


@pytest.fixture
def sample_draft_input():
    """샘플 draft 입력"""
    return DraftOrchestrationInput(
        user_id=1,
        topic_id=100,
        prompt="Write about Python async programming",
        selected_contents=[
            {"content_id": 1, "title": "Content 1", "summary": "Summary 1"},
            {"content_id": 2, "title": "Content 2", "summary": "Summary 2"},
        ],
        retrieval_mode=RetrievalMode.AUTO,
    )


def test_build_draft_plan_structure(orchestrator, sample_draft_input):
    """Draft plan 구조 검증 - 2 stages, correct order"""
    plan = orchestrator._build_draft_plan(sample_draft_input)

    # Plan ID 형식
    assert plan.plan_id.startswith("plan_")
    assert plan.request_type == "draft"
    assert plan.retrieval_mode == RetrievalMode.AUTO

    # 2 stages: summarizer -> writer
    assert len(plan.stages) == 2

    # Stage 1: summarizer
    stage1 = plan.stages[0]
    assert stage1.index == 1
    assert stage1.parallel is False
    assert len(stage1.agents) == 1
    assert stage1.agents[0].agent == "summarizer"

    # Stage 2: writer
    stage2 = plan.stages[1]
    assert stage2.index == 2
    assert stage2.parallel is False
    assert len(stage2.agents) == 1
    assert stage2.agents[0].agent == "writer"


def test_build_draft_plan_metadata(orchestrator, sample_draft_input):
    """Plan metadata 검증"""
    plan = orchestrator._build_draft_plan(sample_draft_input)

    # Metadata에 topic_id, selected_content_count 포함
    assert plan.metadata["topic_id"] == 100
    assert plan.metadata["selected_content_count"] == 2


def test_build_draft_plan_agent_specs(orchestrator, sample_draft_input):
    """AgentSpec reason 필드 검증"""
    plan = orchestrator._build_draft_plan(sample_draft_input)

    # Summarizer reason
    summarizer_spec = plan.stages[0].agents[0]
    assert summarizer_spec.reason == "선택된 콘텐츠 요약"

    # Writer reason
    writer_spec = plan.stages[1].agents[0]
    assert writer_spec.reason == "초안 생성"


@pytest.mark.asyncio
async def test_emit_plan_event(orchestrator, sample_draft_input):
    """Plan 이벤트 전송 검증"""
    plan = orchestrator._build_draft_plan(sample_draft_input)

    # 이벤트 캡처를 위한 리스트
    events = []

    async def mock_callback(event):
        events.append(event)

    # 이벤트 발송
    await orchestrator._emit_plan_event(plan, mock_callback)

    # 이벤트 검증
    assert len(events) == 1
    event = events[0]

    assert event.event == "plan"
    assert event.data["plan_id"] == plan.plan_id
    assert event.data["retrieval_mode"] == "auto"
    assert len(event.data["stages"]) == 2

    # Stage 구조 검증
    stage1_data = event.data["stages"][0]
    assert stage1_data["index"] == 1
    assert stage1_data["parallel"] is False
    assert len(stage1_data["agents"]) == 1
    assert stage1_data["agents"][0]["agent"] == "summarizer"
    assert stage1_data["agents"][0]["reason"] == "선택된 콘텐츠 요약"


@pytest.mark.asyncio
async def test_emit_plan_event_no_callback(orchestrator, sample_draft_input):
    """Callback이 없으면 이벤트를 발송하지 않음"""
    plan = orchestrator._build_draft_plan(sample_draft_input)

    # callback=None 일 때 에러 없이 통과해야 함
    await orchestrator._emit_plan_event(plan, None)


def test_build_draft_plan_retrieval_mode_variants(orchestrator):
    """다양한 RetrievalMode 검증"""
    modes = [
        RetrievalMode.AUTO,
        RetrievalMode.RAG_ONLY,
        RetrievalMode.WEB_ONLY,
        RetrievalMode.BOTH,
    ]

    for mode in modes:
        input_data = DraftOrchestrationInput(
            user_id=1,
            topic_id=100,
            prompt="Test",
            retrieval_mode=mode,
        )
        plan = orchestrator._build_draft_plan(input_data)
        assert plan.retrieval_mode == mode


def test_draft_input_defaults():
    """DraftOrchestrationInput 기본값 검증"""
    input_data = DraftOrchestrationInput(
        user_id=1,
        topic_id=100,
        prompt="Test prompt",
    )

    # 기본값 검증
    assert input_data.selected_contents == []
    assert input_data.retrieval_mode == RetrievalMode.AUTO
    assert input_data.stream is False
    assert input_data.verbose is False
    assert input_data.metadata == {}
    assert input_data.request_id  # UUID hex 생성됨


def test_draft_input_request_id_unique():
    """request_id가 자동으로 고유하게 생성되는지 검증"""
    input1 = DraftOrchestrationInput(
        user_id=1,
        topic_id=100,
        prompt="Test",
    )
    input2 = DraftOrchestrationInput(
        user_id=1,
        topic_id=100,
        prompt="Test",
    )

    # 각기 다른 request_id 생성됨
    assert input1.request_id != input2.request_id
