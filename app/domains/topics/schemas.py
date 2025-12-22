"""Topics 도메인 요청/응답 스키마"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domains.topics.orchestration.models import RetrievalMode


class SelectedContent(BaseModel):
    """Spring 서버에서 전달되는 선택 콘텐츠"""

    content_id: int
    title: str
    summary: str
    full_content: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TopicsUsage(BaseModel):
    """AI usage/WTU 정보"""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_wtu: int = 0
    agents: dict[str, Any] = Field(default_factory=dict)


class TopicsAskResponse(BaseModel):
    """ask API 응답"""

    answer_md: str | None = None
    warnings: list[str] = Field(default_factory=list)
    usage: TopicsUsage | None = None


class TopicsDraftResponse(BaseModel):
    """draft API 응답"""

    title: str | None = None
    draft_md: str | None = None
    warnings: list[str] = Field(default_factory=list)
    usage: TopicsUsage | None = None


class BaseTopicsRequest(BaseModel):
    """공통 요청 필드"""

    user_id: int
    topic_id: int
    stream: bool = False
    verbose: bool = False
    # Stage 1: model_alias는 Optional이며 제공되어도 무시됨
    model_alias: str | None = None


class TopicsAskRequest(BaseTopicsRequest):
    """선택 콘텐츠 기반 ask 요청"""

    prompt: str
    selected_contents: list[SelectedContent]
    retrieval_mode: RetrievalMode = RetrievalMode.AUTO


class TopicsDraftRequest(BaseTopicsRequest):
    """선택 콘텐츠 기반 draft 요청"""

    prompt: str
    selected_contents: list[SelectedContent]
