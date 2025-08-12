from sqlalchemy import JSON, Column, String, Text, DateTime, Integer, Boolean, ForeignKey, Index, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, validates
from pgvector.sqlalchemy import Vector

from app.core.database import Base


class User(Base):
    """사용자 기본 정보 테이블"""
    __tablename__ = "users"
    
    # 서비스 서버의 사용자 ID와 동일한 Long 사용
    # NOTE: AI 서비스에 필요한 최소 정보만 저장, 필요한 경우 추후 추가
    id = Column(Integer, primary_key=True, comment="서비스 서버의 사용자 ID")

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
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment="카테고리 ID")
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

    id = Column(Integer, primary_key=True, autoincrement=True, comment="태그 ID")
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
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    relevance_score = Column(Float, default=1.0, comment="관련도 점수 (0.0-1.0)")
    source = Column(String(20), default="ai", comment="출처: ai, user, system")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # 관계 설정
    item = relationship("Item", back_populates="item_tags")
    tag = relationship("Tag")


class UserCategoryPreference(Base):
    """사용자 카테고리 선호도 테이블"""
    __tablename__ = "user_category_preferences"
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True)
    
    frequency_count = Column(Integer, default=1, comment="사용 빈도")
    preference_score = Column(Float, default=1.0, comment="선호도 점수")
    last_used = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # 관계 설정
    user = relationship("User")
    category = relationship("Category")


class UserTagInteraction(Base):
    """사용자 태그 상호작용 테이블"""
    __tablename__ = "user_tag_interactions"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)

    interaction_count = Column(Integer, default=1, comment="상호작용 횟수")
    preference_score = Column(Float, default=1.0, comment="선호도 점수")
    last_interaction = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    context_category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, comment="상호작용 맥락 카테고리")
    
    # 관계 설정
    user = relationship("User")
    tag = relationship("Tag")
    context_category = relationship("Category")


class Item(Base):
    """아이템 테이블 - 다양한 타입의 콘텐츠를 저장 (웹페이지, PDF, 유튜브, 이미지 등)"""
    __tablename__ = "items"

    # Spring Boot와의 동기화를 위해 기존 ID 사용
    id = Column(Integer, primary_key=True, autoincrement=False, comment="Spring Boot Item ID (동기화)")
    
    # 사용자 관계 추가
    user_id = Column(
        Integer, 
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
    
    # 벡터 임베딩 (pgvector) - 의미 검색용
    embedding_chunks = relationship("ItemEmbeddingMetadata", back_populates="item", cascade="all, delete-orphan")

    # 카테고리 관계를 외래키로 변경
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, comment="카테고리 ID")
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

    # @property
    # def ai_tags(self):
    #     """AI 생성 태그만 반환"""
    #     return [tag for tag in self.tags if tag.tag_type == "ai"]

    # @property
    # def user_tags(self):
    #     """사용자 생성 태그만 반환"""
    #     return [tag for tag in self.tags if tag.tag_type == "user"]


class ItemEmbeddingMetadata(Base):
    """item 임베딩 메타데이터 테이블"""
    __tablename__ = "item_embedding_metadatas"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="임베딩 메타데이터 ID")
    item_id = Column(
        Integer, 
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

    id = Column(Integer, primary_key=True, autoincrement=True, comment="검색 기록 ID")
    
    # 사용자 관계 추가
    user_id = Column(
        Integer, 
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
