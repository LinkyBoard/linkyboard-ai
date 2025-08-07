from sqlalchemy import JSON, Column, String, Text, DateTime, Integer, Boolean, ForeignKey, Index, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
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
    category = Column(String(100), nullable=True, comment="카테고리")
    memo = Column(Text, nullable=True, comment="사용자 메모")
    
    # 원본 콘텐츠 저장 (타입별로 다름)
    raw_content = Column(Text, nullable=True, comment="원본 콘텐츠 (HTML, 텍스트, 메타데이터 등)")
    content_metadata = Column(Text, nullable=True, comment="콘텐츠 메타데이터 (JSON 형태)")
    
    # 벡터 임베딩 (pgvector) - 의미 검색용
    content_embedding = Column(Vector(1536), nullable=True, comment="콘텐츠 벡터 임베딩")
    
    # 태그 정보 (JSON으로 저장) ✨ 핵심 변경
    # user_tags = Column(JSON, nullable=True, comment="사용자 생성 태그 배열 ['tag1', 'tag2']")
    # ai_tags = Column(JSON, nullable=True, comment="AI 생성 태그 객체 [{'tag': 'keyword1', 'confidence': 0.9}]")
    tags = Column(JSON, nullable=True, comment="아이템 태그 (JSON 형태로 저장)")

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
        return self.content_embedding is not None

    # @property
    # def ai_tags(self):
    #     """AI 생성 태그만 반환"""
    #     return [tag for tag in self.tags if tag.tag_type == "ai"]

    # @property
    # def user_tags(self):
    #     """사용자 생성 태그만 반환"""
    #     return [tag for tag in self.tags if tag.tag_type == "user"]

# TODO: AI 태그와 사용자 태그를 별도의 테이블로 분리하는 방안 검토
# 현재는 Item 모델에 JSON 형태로 저장되어 있지만, 별도의 ItemTag 모델로 분리하여 관리하는 것이 더 효율적일 수 있음

# class ItemTag(Base):
#     """아이템 태그 테이블 - AI 키워드 + 사용자 태그 통합 관리"""
#     __tablename__ = "item_tags"

#     id = Column(Integer, primary_key=True, autoincrement=True, comment="아이템 태그 ID")
#     item_id = Column(
#         Integer, 
#         ForeignKey("items.id", ondelete="CASCADE"), 
#         nullable=False, 
#         index=True,
#         comment="아이템 ID (외래키)"
#     )
#     user_id = Column(
#         Integer, 
#         ForeignKey("users.id", ondelete="CASCADE"), 
#         nullable=False, 
#         index=True,
#         comment="사용자 ID (검색 성능 향상용)"
#     )
#     tag = Column(String(100), nullable=False, comment="태그/키워드명")
#     tag_type = Column(
#         String(20), 
#         nullable=False, 
#         default="user", 
#         comment="태그 타입: user(사용자), ai(AI추천), system(시스템)"
#     )
#     confidence_score = Column(
#         Float, 
#         nullable=True, 
#         comment="AI 태그의 신뢰도 점수 (0.0-1.0), 사용자 태그는 NULL"
#     )
#     created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성일시")

#     # 관계 설정
#     item = relationship("Item", back_populates="tags")
#     user = relationship("User")

#     # 인덱스 추가
#     __table_args__ = (
#         Index('ix_item_tags_user_tag', 'user_id', 'tag'),
#         Index('ix_item_tags_user_type', 'user_id', 'tag_type'),
#         Index('ix_item_tags_tag', 'tag'),
#         Index('ix_item_tags_type', 'tag_type'),
#         Index('ix_item_tags_item_tag', 'item_id', 'tag', unique=True),
#         Index('ix_item_tags_confidence', 'confidence_score'),
#         Index('ix_item_tags_type_confidence', 'tag_type', 'confidence_score'),
#     )

#     def __repr__(self):
#         confidence_str = f", confidence={self.confidence_score:.2f}" if self.confidence_score else ""
#         return f"<ItemTag(item_id={self.item_id}, tag='{self.tag}', type='{self.tag_type}'{confidence_str})>"

#     @property
#     def is_ai_tag(self) -> bool:
#         """AI 생성 태그인지 확인"""
#         return self.tag_type == "ai"

#     @property
#     def is_high_confidence(self) -> bool:
#         """고신뢰도 AI 태그인지 확인 (0.7 이상)"""
#         return self.confidence_score is not None and self.confidence_score >= 0.7


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
        comment="검색 타입: semantic(의미검색), keyword(키워드검색), mixed(복합검색)"
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
