"""Contents 도메인 스키마 정의

콘텐츠 동기화 및 관리를 위한 Pydantic 스키마입니다.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.domains.contents.models import (
    ContentType,
    EmbeddingStatus,
    SummaryStatus,
)

# Request Schemas


class WebpageSyncRequest(BaseModel):
    """웹페이지 콘텐츠 동기화 요청"""

    content_id: int = Field(..., gt=0, description="Spring Boot 콘텐츠 ID")
    user_id: int = Field(..., gt=0, description="사용자 ID")
    url: HttpUrl = Field(..., description="웹페이지 URL")
    content_hash: str = Field(
        ..., min_length=64, max_length=64, description="콘텐츠 해시 (SHA-256)"
    )
    title: str = Field(..., min_length=1, max_length=500, description="제목")
    summary: Optional[str] = Field(None, description="요약")
    tags: Optional[list[str]] = Field(None, description="태그 목록")
    category: Optional[str] = Field(None, max_length=100, description="카테고리")
    thumbnail: Optional[HttpUrl] = Field(None, description="썸네일 URL")
    memo: Optional[str] = Field(None, description="사용자 메모")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is not None and len(v) > 50:
            raise ValueError("태그는 최대 50개까지 허용됩니다.")
        return v


class YouTubeSyncRequest(BaseModel):
    """YouTube 콘텐츠 동기화 요청"""

    content_id: int = Field(..., gt=0, description="Spring Boot 콘텐츠 ID")
    user_id: int = Field(..., gt=0, description="사용자 ID")
    url: HttpUrl = Field(..., description="YouTube URL")
    content_hash: str = Field(
        ..., min_length=64, max_length=64, description="콘텐츠 해시 (SHA-256)"
    )
    title: str = Field(..., min_length=1, max_length=500, description="제목")
    summary: Optional[str] = Field(None, description="요약")
    tags: Optional[list[str]] = Field(None, description="태그 목록")
    category: Optional[str] = Field(None, max_length=100, description="카테고리")
    thumbnail: Optional[HttpUrl] = Field(None, description="썸네일 URL")
    memo: Optional[str] = Field(None, description="사용자 메모")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is not None and len(v) > 50:
            raise ValueError("태그는 최대 50개까지 허용됩니다.")
        return v


class PDFSyncRequest(BaseModel):
    """PDF 콘텐츠 동기화 요청 (파일 업로드 별도)"""

    content_id: int = Field(..., gt=0, description="Spring Boot 콘텐츠 ID")
    user_id: int = Field(..., gt=0, description="사용자 ID")
    title: str = Field(..., min_length=1, max_length=500, description="제목")
    summary: Optional[str] = Field(None, description="요약")
    tags: Optional[list[str]] = Field(None, description="태그 목록")
    category: Optional[str] = Field(None, max_length=100, description="카테고리")
    memo: Optional[str] = Field(None, description="사용자 메모")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is not None and len(v) > 50:
            raise ValueError("태그는 최대 50개까지 허용됩니다.")
        return v


class ContentDeleteRequest(BaseModel):
    """콘텐츠 삭제 요청"""

    content_ids: list[int] = Field(
        ..., min_length=1, max_length=100, description="삭제할 콘텐츠 ID 목록"
    )
    user_id: int = Field(..., gt=0, description="사용자 ID")

    @field_validator("content_ids")
    @classmethod
    def validate_content_ids(cls, v: list[int]) -> list[int]:
        if len(v) > 100:
            raise ValueError("한 번에 최대 100개의 콘텐츠만 삭제할 수 있습니다.")
        return v


class ContentListRequest(BaseModel):
    """콘텐츠 목록 조회 요청 (필터)"""

    content_type: Optional[ContentType] = Field(None, description="콘텐츠 타입 필터")
    category: Optional[str] = Field(
        None, max_length=100, description="카테고리 필터"
    )
    tags: Optional[list[str]] = Field(None, description="태그 필터 (OR 조건)")
    date_from: Optional[datetime] = Field(None, description="시작 날짜 필터")
    date_to: Optional[datetime] = Field(None, description="종료 날짜 필터")


# Response Schemas


class ContentResponse(BaseModel):
    """콘텐츠 응답"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    content_type: ContentType
    summary_status: SummaryStatus
    embedding_status: EmbeddingStatus
    source_url: Optional[str] = None
    file_hash: Optional[str] = None
    title: str
    summary: Optional[str] = None
    thumbnail: Optional[str] = None
    memo: Optional[str] = None
    tags: Optional[list[str]] = None
    category: Optional[str] = None
    raw_source: Optional[str] = None
    raw_content: Optional[str] = None
    extraction_method: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


class ContentSyncResponse(BaseModel):
    """콘텐츠 동기화 응답"""

    content_id: int = Field(..., description="생성/업데이트된 콘텐츠 ID")
    file_hash: Optional[str] = Field(None, description="파일 해시 (PDF만)")


class ContentDeleteResponse(BaseModel):
    """콘텐츠 삭제 응답"""

    deleted_count: int = Field(..., description="실제 삭제된 콘텐츠 수")
    failed_items: list[int] = Field(
        default_factory=list, description="삭제 실패한 콘텐츠 ID 목록"
    )
    total_requested: int = Field(..., description="요청된 총 콘텐츠 수")
