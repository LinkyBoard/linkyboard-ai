"""Contents 도메인 모델 정의

웹페이지, YouTube, PDF 콘텐츠를 관리하는 통합 모델입니다.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import ARRAY, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContentType(str, Enum):
    """콘텐츠 타입"""

    WEBPAGE = "webpage"
    YOUTUBE = "youtube"
    PDF = "pdf"


class ProcessingStatus(str, Enum):
    """AI 처리 상태"""

    RAW = "raw"  # 원본 저장됨, AI 처리 대기
    PROCESSED = "processed"  # 요약/태그 추출 완료
    EMBEDDED = "embedded"  # 벡터 임베딩 생성 완료
    FAILED = "failed"  # 처리 실패


class Content(Base):
    """콘텐츠 모델 (웹페이지, YouTube, PDF 통합)

    모든 타입의 콘텐츠를 단일 테이블로 관리합니다.
    - 웹페이지/YouTube: source_url 필수, file_hash NULL
    - PDF: file_hash 필수, source_url NULL
    """

    __tablename__ = "contents"

    # Primary Key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="콘텐츠 ID",
    )

    # Foreign Key
    user_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="사용자 ID (Spring Boot 동기화)",
    )

    # Content Type & Processing Status
    content_type: Mapped[ContentType] = mapped_column(
        String(20),
        nullable=False,
        comment="콘텐츠 타입 (webpage/youtube/pdf)",
    )
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        String(20),
        nullable=False,
        default=ProcessingStatus.RAW,
        server_default="raw",
        comment="AI 처리 상태",
    )

    # Source Information (웹페이지/YouTube만)
    source_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="원본 URL (웹페이지/YouTube만)",
    )

    # File Information (PDF만)
    file_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="파일 해시 SHA-256 (PDF만)",
    )

    # Content Metadata
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="콘텐츠 제목",
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="AI 생성 또는 사용자 확정 요약",
    )
    thumbnail: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="썸네일 URL",
    )

    # User Annotations
    memo: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="사용자 메모",
    )
    tags: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
        comment="태그 목록 (PostgreSQL ARRAY)",
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="카테고리",
    )

    # Raw Data
    raw_source: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="원본 HTML/자막 (웹페이지/YouTube만)",
    )
    raw_content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="AI 추출 텍스트",
    )
    extraction_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="추출 방법 (AI 모델명 등)",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="생성 일시",
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
        comment="수정 일시",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="삭제 일시 (Soft Delete)",
    )

    # Indexes
    __table_args__ = (
        Index(
            "ix_contents_user_id_not_deleted",
            "user_id",
            postgresql_where=(deleted_at.is_(None)),
        ),
        Index("ix_contents_source_url", "source_url"),
        Index("ix_contents_content_type", "content_type", "user_id"),
        Index("ix_contents_processing_status", "processing_status"),
        Index("ix_contents_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Content(id={self.id}, type={self.content_type}, "
            f"user_id={self.user_id}, status={self.processing_status})>"
        )
