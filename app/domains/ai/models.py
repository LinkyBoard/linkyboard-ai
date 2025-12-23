"""AI 도메인 데이터 모델

이 모듈은 AI 기능을 위한 데이터베이스 모델을 정의합니다:
- ContentEmbeddingMetadata: 콘텐츠 임베딩 메타데이터
- ChunkStrategy: 청크 분할 전략
- SummaryCache: 요약 캐시
- Tag: 태그 마스터 (개인화 추천용)
- UserTagUsage: 사용자 태그 사용 통계
- Category: 카테고리 마스터 (개인화 추천용)
- UserCategoryUsage: 사용자 카테고리 사용 통계
- ModelCatalog: AI 모델 카탈로그 (가격 정보 및 WTU 가중치)

주의:
- Contents 테이블의 tags/category는 PostgreSQL ARRAY 타입 문자열
- Tag/Category 마스터 테이블은 임베딩 기반 개인화 추천용
"""
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContentEmbeddingMetadata(Base):
    """콘텐츠 임베딩 메타데이터

    콘텐츠를 청크로 분할하고 각 청크의 임베딩을 저장합니다.
    벡터 검색에 사용됩니다.
    """

    __tablename__ = "content_embedding_metadatas"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    content_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("contents.id"),
        nullable=False,
        index=True,
        comment="연결된 콘텐츠 ID",
    )
    strategy_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("chunk_strategies.id"),
        nullable=True,
        comment="사용된 청크 전략 ID",
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="청크 순서"
    )
    chunk_content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="청크 텍스트 내용"
    )
    start_position: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="원본 텍스트에서의 시작 위치"
    )
    end_position: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="원본 텍스트에서의 종료 위치"
    )
    # pgvector 타입: text-embedding-3-large (3072 차원)
    embedding_vector = mapped_column(
        Vector(3072), nullable=True, comment="임베딩 벡터 (3072 차원)"
    )
    embedding_model: Mapped[str] = mapped_column(
        String(100),
        default="text-embedding-3-large",
        nullable=False,
        comment="임베딩 모델명",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="생성일시",
    )

    def __repr__(self) -> str:
        return (
            f"<ContentEmbeddingMetadata(id={self.id}, "
            f"content_id={self.content_id}, "
            f"chunk_index={self.chunk_index})>"
        )


class ChunkStrategy(Base):
    """청크 분할 전략

    콘텐츠를 어떻게 청크로 분할할지 정의합니다.
    콘텐츠 타입이나 도메인별로 다른 전략을 적용할 수 있습니다.
    """

    __tablename__ = "chunk_strategies"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        comment="전략 이름 (예: default, pdf-academic, webpage-news)",
    )
    content_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="적용할 콘텐츠 타입 (webpage, youtube, pdf)",
    )
    domain: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="적용할 도메인 (예: tech, news, academic)",
    )
    chunk_size: Mapped[int] = mapped_column(
        Integer, default=500, nullable=False, comment="청크 크기 (토큰 수)"
    )
    chunk_overlap: Mapped[int] = mapped_column(
        Integer, default=50, nullable=False, comment="청크 간 겹침 (토큰 수)"
    )
    split_method: Mapped[str] = mapped_column(
        String(50),
        default="token",
        nullable=False,
        comment="분할 방법 (token, sentence, paragraph)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="활성화 여부"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="생성일시",
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
        comment="수정일시",
    )

    def __repr__(self) -> str:
        return (
            f"<ChunkStrategy(id={self.id}, name={self.name}, "
            f"chunk_size={self.chunk_size})>"
        )


class SummaryCache(Base):
    """요약 캐시

    URL이나 파일 해시 기반으로 요약 결과를 캐싱합니다.
    동일한 콘텐츠에 대한 반복 요약을 방지하여 비용을 절감합니다.

    캐시 정책:
    - cache_key: URL 또는 파일의 SHA-256 해시
    - TTL: 30일
    - content_hash로 변경 감지
    """

    __tablename__ = "summary_cache"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    cache_key: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        comment="캐시 키 (URL 또는 파일 해시의 SHA-256)",
    )
    cache_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="캐시 타입 (webpage, youtube, pdf)",
    )
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="콘텐츠 해시 (변경 감지용)"
    )
    extracted_text: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="추출된 텍스트"
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="생성된 요약"
    )
    candidate_tags = mapped_column(
        ARRAY(String),
        nullable=True,
        comment="추천 태그 후보 (PostgreSQL ARRAY)",
    )
    candidate_categories = mapped_column(
        ARRAY(String),
        nullable=True,
        comment="추천 카테고리 후보 (PostgreSQL ARRAY)",
    )
    chunk_embeddings: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="청크별 임베딩 정보 (JSONB)"
    )
    wtu_cost: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="원본 생성 시 사용된 WTU (캐시 히트 시 동일 부과)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="생성일시",
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
        comment="수정일시",
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="만료일시 (TTL 30일)"
    )

    def __repr__(self) -> str:
        return (
            f"<SummaryCache(id={self.id}, cache_key={self.cache_key}, "
            f"cache_type={self.cache_type})>"
        )


class Tag(Base):
    """태그 마스터

    전체 시스템에서 사용되는 태그의 마스터 테이블입니다.
    개인화 추천을 위해 각 태그의 임베딩을 저장합니다.

    주의:
    - Contents 테이블의 tags는 PostgreSQL ARRAY(String) 타입
    - 이 테이블은 임베딩 기반 개인화 추천 전용
    - 태그 문자열로 조회 → 임베딩 벡터 활용 → 유사 태그 추천
    """

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    tag_name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, comment="태그 이름"
    )
    # 태그용 소형 임베딩 (1536 차원)
    embedding_vector = mapped_column(
        Vector(1536),
        nullable=True,
        comment="태그 임베딩 벡터 (1536 차원)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="생성일시",
    )

    def __repr__(self) -> str:
        return f"<Tag(id={self.id}, tag_name={self.tag_name})>"


class UserTagUsage(Base):
    """사용자 태그 사용 통계

    사용자별로 태그를 얼마나 자주 사용했는지 추적합니다.
    개인화된 태그 추천에 사용됩니다.

    개인화 알고리즘:
    - score = 임베딩 유사도 × log(use_count + 1)
    - 유사도: 후보 태그 vs 사용자 기존 태그
    - 빈도: 로그 스케일로 과도한 편향 방지
    """

    __tablename__ = "user_tag_usage"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True, comment="사용자 ID"
    )
    tag_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tags.id"),
        nullable=False,
        comment="태그 ID",
    )
    use_count: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, comment="사용 횟수"
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="마지막 사용일시"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "tag_id", name="uq_user_tag"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserTagUsage(id={self.id}, user_id={self.user_id}, "
            f"tag_id={self.tag_id}, use_count={self.use_count})>"
        )


class Category(Base):
    """카테고리 마스터

    전체 시스템에서 사용되는 카테고리의 마스터 테이블입니다.
    개인화 추천을 위해 각 카테고리의 임베딩을 저장합니다.

    주의:
    - Contents 테이블의 category는 String 타입
    - 이 테이블은 임베딩 기반 개인화 추천 전용
    - 카테고리 문자열로 조회 → 임베딩 벡터 활용 → 유사 카테고리 추천
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    category_name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        comment="카테고리 이름",
    )
    # 카테고리용 소형 임베딩 (1536 차원)
    embedding_vector = mapped_column(
        Vector(1536),
        nullable=True,
        comment="카테고리 임베딩 벡터 (1536 차원)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="생성일시",
    )

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, category_name={self.category_name})>"


class UserCategoryUsage(Base):
    """사용자 카테고리 사용 통계

    사용자별로 카테고리를 얼마나 자주 사용했는지 추적합니다.
    개인화된 카테고리 추천에 사용됩니다.

    개인화 알고리즘:
    - score = 임베딩 유사도 × log(use_count + 1)
    - 유사도: 후보 카테고리 vs 사용자 기존 카테고리
    - 빈도: 로그 스케일로 과도한 편향 방지
    """

    __tablename__ = "user_category_usage"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True, comment="사용자 ID"
    )
    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("categories.id"),
        nullable=False,
        comment="카테고리 ID",
    )
    use_count: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, comment="사용 횟수"
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="마지막 사용일시"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "category_id", name="uq_user_category"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserCategoryUsage(id={self.id}, user_id={self.user_id}, "
            f"category_id={self.category_id}, use_count={self.use_count})>"
        )


class ModelCatalog(Base):
    """AI 모델 카탈로그

    모델별 가격 정보와 WTU 가중치를 관리합니다.
    """

    __tablename__ = "model_catalog"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    alias: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        comment="모델 별칭 (gpt-4o-mini, claude-4.5-haiku)",
    )
    provider: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="제공자 (openai, anthropic, google, perplexity)",
    )
    model_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="실제 모델명"
    )
    model_type: Mapped[str] = mapped_column(
        String(50),
        default="llm",
        nullable=False,
        comment="모델 타입 (llm, embedding, search)",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="모델 설명"
    )

    # 가격 정보 (1M tokens 기준 USD)
    input_price_per_1m: Mapped[float] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        comment="입력 토큰 1M당 가격 (USD)",
    )
    output_price_per_1m: Mapped[float] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        comment="출력 토큰 1M당 가격 (USD)",
    )

    # WTU 가중치 (입력/출력 분리, 기준 모델 대비)
    input_wtu_multiplier: Mapped[float] = mapped_column(
        Numeric(6, 2),
        nullable=False,
        server_default="1.00",
        comment="입력 토큰 WTU 가중치 (기준 모델 = 1.00)",
    )
    output_wtu_multiplier: Mapped[float] = mapped_column(
        Numeric(6, 2),
        nullable=False,
        server_default="1.00",
        comment="출력 토큰 WTU 가중치 (기준 모델 = 1.00)",
    )

    max_context_tokens: Mapped[int] = mapped_column(
        Integer, default=128000, nullable=False, comment="최대 컨텍스트 토큰"
    )

    # Fallback 설정
    tier: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="LLM 티어 (light, standard, premium, search, embedding)",
    )
    fallback_priority: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="티어 내 fallback 우선순위 (낮을수록 먼저 시도, null은 fallback 미사용)",
    )

    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="기본 모델 여부"
    )
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="사용 가능 여부",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="생성일시",
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
        comment="수정일시",
    )

    def __repr__(self) -> str:
        return (
            f"<ModelCatalog(id={self.id}, alias={self.alias}, "
            f"provider={self.provider}, "
            f"input_wtu={self.input_wtu_multiplier}, "
            f"output_wtu={self.output_wtu_multiplier})>"
        )
