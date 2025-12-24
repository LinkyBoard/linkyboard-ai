"""토픽 오케스트레이션 공용 모델

ExecutionPlan/Stage/AgentResult 등 오케스트레이션에서 사용하는
핵심 타입을 정의한다. Phase 1.0(고정 파이프라인)부터 Phase 1.5(동적 플래너)
까지 동일한 구조를 재사용할 수 있도록 느슨한 스키마만 마련한다.

Note: AgentContext는 원래 agents/base.py에 있었으나, 순환 참조 방지를 위해 여기로 이동
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class AgentContext(BaseModel):
    """에이전트 실행 컨텍스트"""

    model_config = {"arbitrary_types_allowed": True}

    request_id: str
    user_id: int
    prompt: str
    session: "AsyncSession"
    additional_data: dict[str, Any] = Field(default_factory=dict)


class RetrievalMode(str, Enum):
    """컨텍스트 소스 선택 모드"""

    AUTO = "auto"
    RAG_ONLY = "rag_only"
    WEB_ONLY = "web_only"
    BOTH = "both"


class AgentExecutionStatus(str, Enum):
    """에이전트 실행 상태"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentSpec(BaseModel):
    """실행 계획에 포함되는 에이전트 메타 정보"""

    agent: str = Field(..., description="에이전트 이름")
    reason: str | None = Field(default=None, description="해당 에이전트를 선택한 이유")
    options: dict[str, Any] = Field(
        default_factory=dict, description="추가 실행 옵션"
    )


class PlanStage(BaseModel):
    """에이전트 Stage 정의"""

    index: int = Field(..., description="Stage 순서 (1 기반)")
    parallel: bool = Field(
        default=False, description="동일 Stage 내 에이전트 병렬 실행 여부"
    )
    agents: list[AgentSpec] = Field(
        default_factory=list, description="Stage 내 실행할 에이전트 목록"
    )


class ExecutionPlan(BaseModel):
    """플래너가 반환하는 최종 실행 계획"""

    plan_id: str
    request_type: Literal["draft", "ask"]
    retrieval_mode: RetrievalMode = RetrievalMode.AUTO
    stages: list[PlanStage] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentUsage(BaseModel):
    """에이전트별 사용량"""

    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    wtu: int = 0


class UsageSummary(BaseModel):
    """오케스트레이션 전체 사용량"""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_wtu: int = 0
    agents: dict[str, AgentUsage] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """각 에이전트 실행 결과"""

    agent: str
    status: AgentExecutionStatus
    success: bool
    skipped: bool = False
    warning: str | None = None
    content: str | None = None
    output: dict[str, Any] | None = None
    error: str | None = None
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class ExecutionResult(BaseModel):
    """Executor가 반환하는 최종 결과"""

    plan_id: str
    results: list[AgentResult] = Field(default_factory=list)
    usage: UsageSummary = Field(default_factory=UsageSummary)
    final_output: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)


class OrchestrationContext(BaseModel):
    """Executor 실행에 필요한 공용 컨텍스트"""

    request_id: str
    user_id: int
    topic_id: int | None = None
    prompt: str | None = None
    selected_contents: list[dict[str, Any]] = Field(default_factory=list)
    stream: bool = False
    verbose: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class StreamEvent(BaseModel):
    """SSE로 전송할 이벤트"""

    event: str
    data: dict[str, Any]


EventCallback = Callable[[StreamEvent], Awaitable[None]]


__all__ = [
    "AgentContext",
    "AgentExecutionStatus",
    "AgentResult",
    "AgentSpec",
    "AgentUsage",
    "EventCallback",
    "ExecutionPlan",
    "ExecutionResult",
    "OrchestrationContext",
    "PlanStage",
    "RetrievalMode",
    "StreamEvent",
    "UsageSummary",
]
