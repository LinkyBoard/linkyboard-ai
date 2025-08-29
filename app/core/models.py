from typing import List, Dict, Any
from sqlalchemy import JSON, Column, String, Text, DateTime, Integer, BigInteger, Boolean, ForeignKey, Index, Float, Date, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, validates
from pgvector.sqlalchemy import Vector

from app.core.database import Base


class User(Base):
    """사용자 기본 정보 테이블"""
    __tablename__ = "users"
    
    # 서비스 서버의 사용자 ID와 동일한 Long 사용
    # NOTE: AI 서비스에 필요한 최소 정보만 저장, 필요한 경우 추후 추가
    id = Column(BigInteger, primary_key=True, comment="서비스 서버의 사용자 ID")

    # AI 서비스 전용 설정
    ai_preferences = Column(Text, nullable=True, comment="AI 개인화 설정 (JSON)")
    embedding_model_version = Column(String(50), nullable=True, comment="사용 중인 임베딩 모델 버전")
    
    # 상태 관리
    is_active = Column(Boolean, default=True, nullable=False, comment="활성 상태")
    last_sync_at = Column(DateTime(timezone=True), nullable=True, comment="서비스 서버와 마지막 동기화 시간")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # 관계 설정
    items = relationship("Item", back_populates="user", cascade="all, delete-orphan")
    search_histories = relationship("SearchHistory", back_populates="user")
    
    __table_args__ = (
        Index('ix_users_active', 'is_active'),
        Index('ix_users_sync_time', 'last_sync_at'),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, active={self.is_active})>"


class Category(Base):
    """카테고리 테이블 - 벡터 임베딩 포함"""
    __tablename__ = "categories"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="카테고리 ID")
    name = Column(String(100), unique=True, nullable=False, comment="카테고리명")
    # description = Column(Text, nullable=True, comment="카테고리 설명")
    embedding = Column(Vector(1536), nullable=True, comment="카테고리 임베딩 벡터")
    
    # 메타데이터
    frequency_count = Column(Integer, default=0, comment="사용 빈도")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # 관계 설정
    items = relationship("Item", back_populates="category_ref")
    
    __table_args__ = (
        Index('ix_categories_name', 'name'),
        Index('ix_categories_frequency', 'frequency_count'),
    )


class Tag(Base):
    """태그 테이블 - 벡터 임베딩 포함"""
    __tablename__ = "tags"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="태그 ID")
    name = Column(String(255), unique=True, nullable=False, comment="태그명")
    embedding = Column(Vector(1536), nullable=True, comment="태그 임베딩 벡터")

    # 통계 정보
    frequency_global = Column(Integer, default=0, comment="전체 사용 빈도")
    user_count = Column(Integer, default=0, comment="사용한 사용자 수")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    __table_args__ = (
        Index('ix_tags_name', 'name'),
        Index('ix_tags_frequency', 'frequency_global'),
    )


class ItemTags(Base):
    """아이템-태그 연결 테이블"""
    __tablename__ = "item_tags"

    # NOTE : 유저 아이디 추가 고려
    item_id = Column(BigInteger, ForeignKey("items.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(BigInteger, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    relevance_score = Column(Float, default=1.0, comment="관련도 점수 (0.0-1.0)")
    source = Column(String(20), default="ai", comment="출처: ai, user")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # 관계 설정
    item = relationship("Item", back_populates="item_tags")
    tag = relationship("Tag")


class UserCategoryPreference(Base):
    """사용자 카테고리 선호도 테이블"""
    __tablename__ = "user_category_preferences"
    
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    category_id = Column(BigInteger, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True)
    
    frequency_count = Column(Integer, default=1, comment="사용 빈도")
    preference_score = Column(Float, default=1.0, comment="선호도 점수")
    last_used = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # 관계 설정
    user = relationship("User")
    category = relationship("Category")


class UserTagInteraction(Base):
    """사용자 태그 상호작용 테이블"""
    __tablename__ = "user_tag_interactions"

    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(BigInteger, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)

    interaction_count = Column(Integer, default=1, comment="상호작용 횟수")
    preference_score = Column(Float, default=1.0, comment="선호도 점수")
    last_interaction = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    context_category_id = Column(BigInteger, ForeignKey("categories.id"), nullable=True, comment="상호작용 맥락 카테고리")
    
    # 관계 설정
    user = relationship("User")
    tag = relationship("Tag")
    context_category = relationship("Category")


class Item(Base):
    """아이템 테이블 - 다양한 타입의 콘텐츠를 저장 (웹페이지, PDF, 유튜브, 이미지 등)"""
    __tablename__ = "items"

    # Spring Boot와의 동기화를 위해 기존 ID 사용
    id = Column(BigInteger, primary_key=True, autoincrement=False, comment="Spring Boot Item ID (동기화)")
    
    # 사용자 관계 추가
    user_id = Column(
        BigInteger, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True,
        comment="사용자 ID (외래키)"
    )
    
    # 콘텐츠 타입 및 소스 정보
    item_type = Column(
        String(20), 
        nullable=False, 
        default="webpage", 
        comment="아이템 타입: webpage(웹페이지), pdf(PDF문서), youtube(유튜브), image(이미지), document(문서) 등"
    )
    source_url = Column(String(2048), nullable=False, index=True, comment="원본 소스 URL")
    
    # 기본 메타데이터 (모든 타입 공통)
    title = Column(String(500), nullable=False, comment="제목")
    thumbnail = Column(Text, nullable=True, comment="썸네일 이미지 (base64 또는 URL)")
    description = Column(Text, nullable=True, comment="설명 또는 요약")
    summary = Column(Text, nullable=True, comment="요약")
    memo = Column(Text, nullable=True, comment="사용자 메모")
    
    # 원본 콘텐츠 저장 (타입별로 다름)
    raw_content = Column(Text, nullable=True, comment="원본 콘텐츠 (HTML, 텍스트, 메타데이터 등)")
    content_metadata = Column(Text, nullable=True, comment="콘텐츠 메타데이터 (JSON 형태)")
    
    # FTS (Full Text Search) 컬럼 - 중복 탐지용
    # PostgreSQL에서 Generated 컬럼으로 생성됨 (마이그레이션에서 처리)
    # fts = Column(TSVector, nullable=True, comment="전문검색용 tsvector (title + description + summary)")
    
    # 벡터 임베딩 (pgvector) - 의미 검색용
    embedding_chunks = relationship("ItemEmbeddingMetadata", back_populates="item", cascade="all, delete-orphan")

    # 카테고리 관계를 외래키로 변경
    category_id = Column(BigInteger, ForeignKey("categories.id"), nullable=True, comment="카테고리 ID")
    category = Column(String(100), nullable=True, comment="카테고리명 (캐시용)")
    
    # 관계 추가
    category_ref = relationship("Category", back_populates="items")
    item_tags = relationship("ItemTags", back_populates="item")


    # 처리 상태 관리
    processing_status = Column(
        String(20), 
        nullable=False, 
        default="raw", 
        comment="처리 상태: raw(원본만), processed(처리완료), summarized(요약완료), embedded(임베딩완료)"
    )
    
    # 메타데이터
    is_active = Column(Boolean, default=True, nullable=False, comment="활성 상태")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성일시")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True, comment="수정일시")

    # 관계 설정
    user = relationship("User", back_populates="items")

    # 추가 인덱스 정의 (검색 성능 향상)
    __table_args__ = (
        Index('ix_items_user_id', 'user_id'),
        Index('ix_items_user_type', 'user_id', 'item_type'),
        Index('ix_items_user_status', 'user_id', 'processing_status'),
        Index('ix_items_source_url', 'source_url', unique=True),  # 사용자별로는 중복 가능하지만 전체적으로는 unique
        Index('ix_items_type', 'item_type'),
        Index('ix_items_category', 'category'),
        Index('ix_items_processing_status', 'processing_status'),
        Index('ix_items_created_at', 'created_at'),
        Index('ix_items_type_status', 'item_type', 'processing_status'),
    )

    def __repr__(self):
        return f"<Item(id={self.id}, type='{self.item_type}', title='{self.title[:30]}...', status='{self.processing_status}')>"

    @property
    def is_summarized(self) -> bool:
        """요약이 완료되었는지 확인"""
        return self.summary is not None and self.category is not None

    @property 
    def is_embedded(self) -> bool:
        """임베딩이 완료되었는지 확인"""
        return len(self.embedding_chunks) > 0

    @property
    def ai_tags(self):
        """AI 생성 태그만 반환"""
        return [item_tag.tag for item_tag in self.item_tags if item_tag.source == "ai"]

    @property
    def user_tags(self):
        """사용자 생성 태그만 반환"""
        return [item_tag.tag for item_tag in self.item_tags if item_tag.source == "user"]
    
    @property
    def all_tags(self):
        """모든 태그 반환"""
        return [item_tag.tag for item_tag in self.item_tags]


class ItemEmbeddingMetadata(Base):
    """item 임베딩 메타데이터 테이블"""
    __tablename__ = "item_embedding_metadatas"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="임베딩 메타데이터 ID")
    item_id = Column(
        BigInteger, 
        ForeignKey("items.id", ondelete="CASCADE"),
        comment="아이템 ID (외래키)"
    )
    embedding_model = Column(String(50), nullable=False, comment="임베딩 모델명")
    embedding_version = Column(String(50), nullable=False, comment="임베딩 모델 버전")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성일시")
    
    # 청크 관련 정보
    chunk_number = Column(Integer, nullable=False, comment="청크 번호 (0부터 시작)")
    chunk_content = Column(Text, nullable=False, comment="청크 텍스트 내용")
    chunk_size = Column(Integer, nullable=True, comment="청크 크기(문자 수)")
    token_count = Column(Integer, nullable=True, comment="토큰 수")
    start_position = Column(Integer, nullable=True, comment="원본에서 시작 위치")
    end_position = Column(Integer, nullable=True, comment="원본에서 끝 위치")

    total_chunks = Column(Integer, nullable=False, comment="총 청크 수")

    # 임베딩 벡터 (pgvector)
    embedding_vector = Column(Vector(1536), nullable=False, comment="아이템 임베딩 벡터")

    # 관계 설정
    item = relationship("Item", back_populates="embedding_chunks")

    __table_args__ = (
        Index('ix_item_embedding_metadatas_item_id', 'item_id'),
        Index('ix_item_embedding_metadatas_item_chunk', 'item_id', 'chunk_number', unique=True),
        Index('ix_item_embedding_metadatas_model_version', 'embedding_model', 'embedding_version'),
        # pgvector 유사도 검색용 인덱스 (별도 DDL 필요)
    )

    @property
    def similarity_threshold(self) -> float:
        """이 청크의 권장 유사도 임계값"""
        return 0.8 if self.chunk_number == 0 else 0.7  # 첫 번째 청크는 더 높은 임계값
    
    @property
    def is_first_chunk(self) -> bool:
        """첫 번째 청크인지 확인 (보통 제목/요약 포함)"""
        return self.chunk_number == 0

    @property
    def chunk_weight(self) -> float:
        """검색 시 가중치 (첫 번째 청크 더 높은 가중치)"""
        return 1.2 if self.is_first_chunk else 1.0
    
    def get_context_preview(self, max_chars: int = 200) -> str:
        """검색 결과 미리보기용 텍스트"""
        return self.chunk_content[:max_chars] + "..." if len(self.chunk_content) > max_chars else self.chunk_content

    @validates('chunk_number')
    def validate_chunk_number(self, key, chunk_number):
        if chunk_number < 0:
            raise ValueError("chunk_number must be >= 0")
        return chunk_number

    @validates('total_chunks')
    def validate_total_chunks(self, key, total_chunks):
        if total_chunks < 1:
            raise ValueError("total_chunks must be >= 1")
        return total_chunks


class SearchHistory(Base):
    """검색 히스토리 테이블 - 사용자 검색 기록 및 성능 분석용"""
    __tablename__ = "search_histories"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="검색 기록 ID")
    
    # 사용자 관계 추가
    user_id = Column(
        BigInteger, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True,
        comment="사용자 ID (외래키)"
    )
    
    query = Column(String(500), nullable=False, comment="검색 쿼리")
    query_embedding = Column(Vector(1536), nullable=True, comment="검색 쿼리 벡터 임베딩")
    search_type = Column(
        String(20), 
        nullable=False, 
        default="semantic", 
        comment="검색 타입: semantic(의미검색), tag(태그검색), mixed(복합검색)"
    )
    result_count = Column(Integer, nullable=False, default=0, comment="검색 결과 수")
    
    # 검색 성능 메트릭
    search_duration_ms = Column(Integer, nullable=True, comment="검색 소요시간(밀리초)")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="검색일시")

    # 관계 설정
    user = relationship("User", back_populates="search_histories")

    # 인덱스 추가
    __table_args__ = (
        Index('ix_search_histories_user_id', 'user_id'),
        Index('ix_search_histories_user_query', 'user_id', 'query'),
        Index('ix_search_histories_query', 'query'),
        Index('ix_search_histories_type', 'search_type'),
        Index('ix_search_histories_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<SearchHistory(id={self.id}, query='{self.query}', type='{self.search_type}', results={self.result_count})>"


class UsageMeter(Base):
    """WTU 사용량 계측 테이블"""
    __tablename__ = "usage_meter"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="사용량 기록 ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="사용자 ID")
    run_id = Column(BigInteger, nullable=True, comment="실행 ID (배치 작업 시)")
    
    # 사용된 모델 정보
    llm_model = Column(String(100), nullable=True, comment="사용된 LLM 모델명")
    embedding_model = Column(String(100), nullable=True, comment="사용된 임베딩 모델명")
    selected_model_id = Column(BigInteger, ForeignKey("model_catalog.id", ondelete="SET NULL"), nullable=True, comment="사용자가 선택한 모델 ID")
    model_weights_snapshot = Column(JSON, nullable=True, comment="실행 시점의 모델 가중치 스냅샷")
    board_id = Column(BigInteger, nullable=True, comment="보드 ID (정책 추적용)")
    
    # 토큰 사용량
    in_tokens = Column(Integer, default=0, nullable=False, comment="입력 토큰 수")
    cached_in_tokens = Column(Integer, default=0, nullable=False, comment="캐시된 입력 토큰 수")
    out_tokens = Column(Integer, default=0, nullable=False, comment="출력 토큰 수")
    embed_tokens = Column(Integer, default=0, nullable=False, comment="임베딩 토큰 수")
    
    # WTU 계산값
    wtu = Column(Integer, default=0, nullable=False, comment="계산된 WTU 값")
    
    # 비용 정보 (참고용)
    estimated_cost_usd = Column(Float, nullable=True, comment="추정 비용 (USD)")
    
    # 계획 월 (해당 월의 첫째 날)
    plan_month = Column(Date, nullable=False, comment="계획 월 (YYYY-MM-01)")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성일시")
    
    # 관계 설정
    user = relationship("User")
    selected_model = relationship("ModelCatalog")
    
    __table_args__ = (
        Index('ix_usage_meter_plan_month', 'plan_month'),
        Index('ix_usage_meter_user_plan_month', 'user_id', 'plan_month'),
        Index('ix_usage_meter_created_at', 'created_at'),
        Index('ix_usage_meter_llm_model', 'llm_model'),
        Index('ix_usage_meter_embedding_model', 'embedding_model'),
        Index('ix_usage_meter_selected_model', 'selected_model_id'),
        Index('ix_usage_meter_board_id', 'board_id'),
    )

    def __repr__(self):
        return f"<UsageMeter(user_id={self.user_id}, wtu={self.wtu}, plan_month={self.plan_month})>"


class DedupSuggestion(Base):
    """중복 후보 제안 테이블"""
    __tablename__ = "dedup_suggestion"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="중복 제안 ID")
    board_id = Column(BigInteger, nullable=False, comment="보드 ID")  # 추후 Board 테이블 생성 시 외래키로 변경
    
    # 중복 후보 문서 ID 배열
    doc_ids = Column(ARRAY(BigInteger), nullable=False, comment="중복 후보 문서 ID 배열 (최소 2개)")
    
    # 유사도 점수 (BM25 기반 정규화)
    score = Column(Float, nullable=False, comment="유사도 점수 (0.0-1.0)")
    
    # 사용자 수락 여부
    accepted = Column(Boolean, default=False, nullable=False, comment="사용자 수락 여부")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성일시")
    
    __table_args__ = (
        Index('ix_dedup_suggestion_board_created', 'board_id', 'created_at'),
        Index('ix_dedup_suggestion_score', 'score'),
        Index('ix_dedup_suggestion_accepted', 'accepted'),
    )

    def __repr__(self):
        return f"<DedupSuggestion(board_id={self.board_id}, docs={len(self.doc_ids)}, score={self.score:.2f})>"


class ModelCatalog(Base):
    """모델 카탈로그 및 WTU 가중치 테이블 (구 ModelPricing)"""
    __tablename__ = "model_catalog"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="모델 카탈로그 ID")
    model_name = Column(String(100), nullable=False, unique=True, comment="모델명 (예: gpt-3.5-turbo, text-embedding-3-small)")
    alias = Column(String(100), nullable=False, comment="모델 별칭 (사용자 친화적 이름)")
    provider = Column(String(50), nullable=False, default="openai", comment="모델 제공자 (openai, anthropic 등)")
    model_type = Column(String(20), nullable=False, comment="모델 유형: llm, embedding")
    role_mask = Column(Integer, nullable=False, default=7, comment="모델 역할 마스크 (1=LLM, 2=embedding, 4=multimodal)")
    status = Column(String(20), nullable=False, default="active", comment="모델 상태 (active, deprecated, beta)")
    version = Column(String(20), nullable=True, comment="모델 버전")
    
    # 원본 가격 정보 (USD per 1M tokens)
    price_input = Column(Float, nullable=True, comment="입력 토큰 가격 (USD/1M)")
    price_output = Column(Float, nullable=True, comment="출력 토큰 가격 (USD/1M)")
    price_embedding = Column(Float, nullable=True, comment="임베딩 가격 (USD/1M)")
    
    # 계산된 WTU 가중치 (reference 모델 대비)
    weight_input = Column(Float, nullable=True, comment="입력 토큰 WTU 가중치")
    weight_output = Column(Float, nullable=True, comment="출력 토큰 WTU 가중치")
    weight_embedding = Column(Float, nullable=True, comment="임베딩 토큰 WTU 가중치")
    
    # 기준 모델 정보
    reference_model = Column(String(100), nullable=False, default="gpt-5-mini", comment="기준 모델명")
    reference_price_input = Column(Float, nullable=False, default=0.25, comment="기준 입력 가격 (USD/1M)")
    reference_price_output = Column(Float, nullable=False, default=2.00, comment="기준 출력 가격 (USD/1M)")
    
    # 설정값
    cached_factor = Column(Float, nullable=False, default=0.1, comment="캐시 토큰 할인율")
    embedding_alpha = Column(Float, nullable=False, default=0.8, comment="임베딩 가중치 조정 계수")
    
    # 상태 관리
    is_active = Column(Boolean, default=True, nullable=False, comment="활성 상태")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성일시")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True, comment="수정일시")
    
    __table_args__ = (
        Index('ix_model_catalog_name', 'model_name'),
        Index('ix_model_catalog_alias', 'alias'),
        Index('ix_model_catalog_provider', 'provider'),
        Index('ix_model_catalog_status', 'status'),
        Index('ix_model_catalog_type_status', 'model_type', 'status'),
    )

    def __repr__(self):
        return f"<ModelCatalog(alias={self.alias}, provider={self.provider}, status={self.status})>"
    
    def calculate_weights(self) -> None:
        """기준 모델 대비 WTU 가중치 계산"""
        # 기본값이 None인 경우 기본값으로 설정
        if self.reference_price_input is None:
            self.reference_price_input = 0.25
        if self.reference_price_output is None:
            self.reference_price_output = 2.00
        if self.embedding_alpha is None:
            self.embedding_alpha = 0.8
        if self.cached_factor is None:
            self.cached_factor = 0.1
            
        if self.model_type == "llm":
            if self.price_input is not None:
                self.weight_input = self.price_input / self.reference_price_input
            if self.price_output is not None:
                self.weight_output = 8.0 * (self.price_output / self.reference_price_output)
        elif self.model_type == "embedding":
            if self.price_embedding is not None:
                self.weight_embedding = self.embedding_alpha * (self.price_embedding / self.reference_price_input)
    
    @property
    def weight_cached_input(self) -> float:
        """캐시된 입력 토큰의 가중치"""
        return (self.weight_input or 0) * self.cached_factor


class ModelWeightHistory(Base):
    """모델 가중치 변경 히스토리 테이블"""
    __tablename__ = "model_weight_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="가중치 히스토리 ID")
    model_id = Column(BigInteger, ForeignKey("model_catalog.id", ondelete="CASCADE"), nullable=False, comment="모델 카탈로그 ID (외래키)")
    w_in = Column(Float, nullable=True, comment="입력 토큰 WTU 가중치")
    w_out = Column(Float, nullable=True, comment="출력 토큰 WTU 가중치")
    w_embed = Column(Float, nullable=True, comment="임베딩 토큰 WTU 가중치")
    reason = Column(Text, nullable=True, comment="가중치 변경 사유")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성일시")
    
    # 관계 설정
    model = relationship("ModelCatalog")
    
    __table_args__ = (
        Index('ix_model_weight_history_model_id', 'model_id'),
        Index('ix_model_weight_history_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<ModelWeightHistory(model_id={self.model_id}, w_in={self.w_in}, w_out={self.w_out})>"


class BoardModelPolicy(Base):
    """보드별 모델 정책 테이블"""
    __tablename__ = "board_model_policy"

    board_id = Column(BigInteger, primary_key=True, comment="보드 ID")
    default_model_id = Column(BigInteger, ForeignKey("model_catalog.id", ondelete="SET NULL"), nullable=True, comment="기본 모델 ID (외래키)")
    allowed_model_ids = Column(ARRAY(BigInteger), nullable=True, comment="허용 모델 ID 배열")
    budget_wtu = Column(Integer, nullable=True, comment="월 예산 WTU")
    confidence_target = Column(Float, nullable=True, comment="품질 목표 점수 (0.0-1.0)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성일시")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True, comment="수정일시")
    
    # 관계 설정
    default_model = relationship("ModelCatalog")
    
    __table_args__ = (
        Index('ix_board_model_policy_default_model', 'default_model_id'),
    )

    def __repr__(self):
        return f"<BoardModelPolicy(board_id={self.board_id}, default_model_id={self.default_model_id})>"


class UserModelPolicy(Base):
    """사용자별 모델 정책 테이블 (선택사항)"""
    __tablename__ = "user_model_policy"

    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, comment="사용자 ID")
    default_model_id = Column(BigInteger, ForeignKey("model_catalog.id", ondelete="SET NULL"), nullable=True, comment="기본 모델 ID (외래키)")
    allowed_model_ids = Column(ARRAY(BigInteger), nullable=True, comment="허용 모델 ID 배열")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성일시")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True, comment="수정일시")
    
    # 관계 설정
    user = relationship("User")
    default_model = relationship("ModelCatalog")
    
    __table_args__ = (
        Index('ix_user_model_policy_default_model', 'default_model_id'),
    )

    def __repr__(self):
        return f"<UserModelPolicy(user_id={self.user_id}, default_model_id={self.default_model_id})>"


class Board(Base):
    """토픽 보드 테이블 - 스프링 서버와 동기화"""
    __tablename__ = "boards"
    
    # 스프링 서버의 보드 ID와 동기화
    id = Column(BigInteger, primary_key=True, autoincrement=False, comment="Spring Boot Board ID (동기화)")
    
    # 사용자 관계
    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="사용자 ID (외래키)"
    )
    
    # 기본 정보
    title = Column(String(200), nullable=False, comment="보드 제목")
    description = Column(Text, nullable=True, comment="보드 설명")
    
    # 동기화 관리
    is_active = Column(Boolean, default=True, nullable=False, comment="활성 상태 (동기화 상태)")
    last_sync_at = Column(DateTime(timezone=True), nullable=True, comment="스프링 서버와 마지막 동기화 시간")
    
    # 시간 정보
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성일시")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True, comment="수정일시")
    
    # 관계 설정
    user = relationship("User")
    board_items = relationship("BoardItem", back_populates="board", cascade="all, delete-orphan")
    board_analytics = relationship("BoardAnalytics", back_populates="board", uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_boards_user_id', 'user_id'),
        Index('ix_boards_sync_time', 'last_sync_at'),
        Index('ix_boards_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Board(id={self.id}, title='{self.title[:30]}...')>"
    
    @property
    def item_count(self) -> int:
        """보드에 포함된 아이템 수"""
        return len(self.board_items)
    
    @property
    def is_analyzed(self) -> bool:
        """분석이 완료되었는지 확인"""
        return self.board_analytics is not None


class BoardItem(Base):
    """보드-아이템 관계 테이블"""
    __tablename__ = "board_items"
    
    # 복합 기본키
    board_id = Column(BigInteger, ForeignKey("boards.id", ondelete="CASCADE"), primary_key=True)
    item_id = Column(BigInteger, ForeignKey("items.id", ondelete="CASCADE"), primary_key=True)
    
    # 보드 내에서의 아이템 정보
    added_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="보드에 추가된 시간")
    
    # 아이템 중요도 (AI 추천에 활용)
    relevance_score = Column(Float, default=1.0, comment="보드 주제와의 관련도 점수 (0.0-1.0)")
    
    # 관계 설정
    board = relationship("Board", back_populates="board_items")
    item = relationship("Item")
    
    __table_args__ = (
        Index('ix_board_items_board_id', 'board_id'),
        Index('ix_board_items_item_id', 'item_id'),
        Index('ix_board_items_added_at', 'added_at'),
    )
    
    def __repr__(self):
        return f"<BoardItem(board_id={self.board_id}, item_id={self.item_id}, relevance={self.relevance_score})>"


class BoardAnalytics(Base):
    """보드 분석 정보 테이블 - AI 분석 결과 저장"""
    __tablename__ = "board_analytics"
    
    board_id = Column(BigInteger, ForeignKey("boards.id", ondelete="CASCADE"), primary_key=True)
    
    # 주제 분석 결과
    topic_embedding = Column(Vector(1536), nullable=True, comment="보드 주제 임베딩 벡터 (아이템들의 가중평균)")
    content_summary = Column(Text, nullable=True, comment="보드 전체 내용 요약")
    
    # 카테고리 및 태그 분포
    dominant_categories = Column(JSON, nullable=True, comment="주요 카테고리 분포 {category: count}")
    tag_distribution = Column(JSON, nullable=True, comment="태그 분포 {tag: weight}")
    
    # 통계 정보
    total_items = Column(Integer, default=0, comment="총 아이템 수")
    total_content_length = Column(Integer, default=0, comment="전체 콘텐츠 길이")
    avg_item_relevance = Column(Float, default=0.0, comment="평균 아이템 관련도")
    
    # 품질 지표
    content_diversity_score = Column(Float, nullable=True, comment="콘텐츠 다양성 점수 (0.0-1.0)")
    topic_coherence_score = Column(Float, nullable=True, comment="주제 일관성 점수 (0.0-1.0)")
    
    # 분석 메타데이터
    analytics_version = Column(String(20), nullable=False, default="1.0", comment="분석 알고리즘 버전")
    last_analyzed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="마지막 분석 시간")
    
    # 관계 설정
    board = relationship("Board", back_populates="board_analytics")
    
    __table_args__ = (
        Index('ix_board_analytics_analyzed_at', 'last_analyzed_at'),
        Index('ix_board_analytics_version', 'analytics_version'),
    )
    
    def __repr__(self):
        return f"<BoardAnalytics(board_id={self.board_id}, items={self.total_items}, coherence={self.topic_coherence_score})>"
    
    @property
    def is_stale(self) -> bool:
        """분석 결과가 오래되었는지 확인 (24시간 기준)"""
        from datetime import datetime, timedelta
        if not self.last_analyzed_at:
            return True
        return datetime.now() - self.last_analyzed_at > timedelta(hours=24)
    
    @property
    def top_categories(self, limit: int = 5) -> List[Dict[str, Any]]:
        """상위 카테고리 목록 반환"""
        if not self.dominant_categories:
            return []
        
        items = list(self.dominant_categories.items())
        items.sort(key=lambda x: x[1], reverse=True)
        return [{"category": cat, "count": count} for cat, count in items[:limit]]
    
    @property
    def top_tags(self, limit: int = 10) -> List[Dict[str, Any]]:
        """상위 태그 목록 반환"""
        if not self.tag_distribution:
            return []
        
        items = list(self.tag_distribution.items())
        items.sort(key=lambda x: x[1], reverse=True)
        return [{"tag": tag, "weight": weight} for tag, weight in items[:limit]]


class UserTokenQuota(Base):
    """사용자 토큰 할당량 및 사용량 추적 테이블"""
    __tablename__ = "user_token_quota"
    
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, comment="사용자 ID")
    plan_month = Column(Date, primary_key=True, comment="계획 월 (YYYY-MM-01)")
    
    # 할당량 정보
    allocated_quota = Column(Integer, nullable=False, default=10000, comment="할당된 토큰 쿼터")
    used_tokens = Column(Integer, nullable=False, default=0, comment="사용된 토큰 수")
    remaining_tokens = Column(Integer, nullable=False, default=10000, comment="남은 토큰 수")
    
    # 충전 기록
    total_purchased = Column(Integer, nullable=False, default=0, comment="총 구매한 토큰 수")
    
    # 상태 관리
    is_active = Column(Boolean, default=True, nullable=False, comment="활성 상태")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성일시")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True, comment="수정일시")
    
    # 관계 설정  
    user = relationship("User")
    # token_purchases 관계는 복잡한 복합키 때문에 제거하고 서비스 레벨에서 처리
    
    __table_args__ = (
        Index('ix_user_token_quota_user_month', 'user_id', 'plan_month'),
        Index('ix_user_token_quota_plan_month', 'plan_month'),
    )
    
    def __repr__(self):
        return f"<UserTokenQuota(user_id={self.user_id}, remaining={self.remaining_tokens})>"
    
    @property
    def usage_percentage(self) -> float:
        """사용률 계산 (0.0-1.0)"""
        if self.allocated_quota == 0:
            return 1.0
        return self.used_tokens / self.allocated_quota
    
    @property
    def is_quota_exceeded(self) -> bool:
        """쿼터 초과 여부"""
        return self.remaining_tokens <= 0
    
    def can_consume(self, token_amount: int) -> bool:
        """토큰 사용 가능 여부 확인"""
        return self.remaining_tokens >= token_amount
    
    def consume_tokens(self, token_amount: int) -> bool:
        """토큰 소비"""
        if not self.can_consume(token_amount):
            return False
        
        self.used_tokens += token_amount
        self.remaining_tokens = max(0, self.allocated_quota - self.used_tokens)
        return True
    
    def add_quota(self, additional_tokens: int):
        """쿼터 추가 (충전)"""
        self.allocated_quota += additional_tokens
        self.remaining_tokens = self.allocated_quota - self.used_tokens
        self.total_purchased += additional_tokens


class TokenPurchase(Base):
    """토큰 구매/충전 기록 테이블"""
    __tablename__ = "token_purchases"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="구매 기록 ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="사용자 ID")
    plan_month = Column(Date, nullable=False, comment="해당 월 (YYYY-MM-01)")
    
    # 구매 정보
    token_amount = Column(Integer, nullable=False, comment="구매한 토큰 수")
    purchase_type = Column(String(20), nullable=False, default="purchase", comment="구매 유형: purchase, bonus, refund")
    
    # 결제 정보 (추후 확장)
    payment_method = Column(String(50), nullable=True, comment="결제 수단")
    payment_amount = Column(Float, nullable=True, comment="결제 금액")
    currency = Column(String(10), nullable=True, default="KRW", comment="통화")
    
    # 상태 관리
    status = Column(String(20), nullable=False, default="completed", comment="상태: pending, completed, failed, refunded")
    transaction_id = Column(String(100), nullable=True, comment="거래 ID")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="구매일시")
    processed_at = Column(DateTime(timezone=True), nullable=True, comment="처리일시")
    
    # 관계 설정
    user = relationship("User")
    # quota 관계는 복잡한 복합키 때문에 제거하고 서비스 레벨에서 처리
    
    __table_args__ = (
        Index('ix_token_purchases_user_id', 'user_id'),
        Index('ix_token_purchases_plan_month', 'plan_month'),
        Index('ix_token_purchases_status', 'status'),
        Index('ix_token_purchases_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<TokenPurchase(user_id={self.user_id}, amount={self.token_amount}, status={self.status})>"


class BoardRecommendationCache(Base):
    """보드별 추천 결과 캐시 테이블"""
    __tablename__ = "board_recommendation_cache"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    board_id = Column(BigInteger, ForeignKey("boards.id", ondelete="CASCADE"), nullable=False)
    
    # 추천 타입 및 결과
    recommendation_type = Column(
        String(50),
        nullable=False,
        comment="추천 타입: related_boards, suggested_items, insights, trends"
    )
    recommendations = Column(JSON, nullable=False, comment="추천 결과 JSON")
    
    # 캐시 관리
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성 시간")
    expires_at = Column(DateTime(timezone=True), nullable=False, comment="만료 시간")
    cache_version = Column(String(20), nullable=False, default="1.0", comment="캐시 버전")
    
    # 성능 메트릭
    generation_time_ms = Column(Integer, nullable=True, comment="생성 소요 시간 (밀리초)")
    confidence_score = Column(Float, nullable=True, comment="추천 신뢰도 점수")
    
    __table_args__ = (
        Index('ix_board_recommendation_cache_board_type', 'board_id', 'recommendation_type'),
        Index('ix_board_recommendation_cache_expires_at', 'expires_at'),
        Index('ix_board_recommendation_cache_generated_at', 'generated_at'),
    )
    
    def __repr__(self):
        return f"<BoardRecommendationCache(board_id={self.board_id}, type='{self.recommendation_type}')>"
    
    @property
    def is_expired(self) -> bool:
        """캐시가 만료되었는지 확인"""
        from datetime import datetime
        return datetime.now() > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """캐시가 유효한지 확인"""
        return not self.is_expired and self.recommendations is not None
