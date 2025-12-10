"""AI 도메인 스키마 정의
"""

from typing import Optional

from pydantic import BaseModel, Field

from app.domains.ai.search.types import SearchFilters


class WebpageSummarizeRequest(BaseModel):
    """웹페이지 요약 요청"""

    url: str = Field(..., description="웹페이지 URL")
    user_id: int = Field(..., description="사용자 ID")
    tag_count: int = Field(5, ge=1, le=20, description="추천 태그 수")
    refresh: bool = Field(False, description="캐시 무시하고 재생성")


class YoutubeSummarizeRequest(BaseModel):
    """YouTube 요약 요청"""

    url: str = Field(..., description="YouTube URL")
    user_id: int
    tag_count: int = Field(5, ge=1, le=20)
    refresh: bool = Field(False)


class PDFSummarizeRequest(BaseModel):
    """PDF 요약 요청"""

    user_id: int
    tag_count: int = Field(5, ge=1, le=20)
    refresh: bool = Field(False)


class SummarizeResponse(BaseModel):
    """요약 응답"""

    content_hash: str
    extracted_text: str
    summary: str
    tags: list[str]
    category: str
    candidate_tags: list[str]
    candidate_categories: list[str]
    cached: bool


class SearchRequest(BaseModel):
    """콘텐츠 검색 요청"""

    query: str = Field(..., description="검색 쿼리", min_length=1)
    user_id: int = Field(..., description="사용자 ID")
    search_mode: str = Field(
        "hybrid",
        description="검색 모드 (vector, keyword, hybrid)",
        pattern="^(vector|keyword|hybrid)$",
    )
    filters: Optional[SearchFilters] = Field(None, description="검색 필터")
    page: int = Field(1, ge=1, description="페이지 번호")
    size: int = Field(20, ge=1, le=100, description="페이지 크기")
    threshold: float = Field(0.5, ge=0.0, le=1.0, description="벡터 검색 유사도 임계값")
    include_chunks: bool = Field(False, description="매칭된 청크 정보 포함 여부")


class SearchResultResponse(BaseModel):
    """검색 결과 응답"""

    content_id: int
    title: str
    summary: Optional[str] = None
    content_type: str
    source_url: Optional[str] = None

    # 검색 모드에 따라 하나의 점수 필드만 존재
    similarity: Optional[float] = Field(
        None, description="벡터 유사도 (0.0~1.0, vector 모드)"
    )
    rank: Optional[float] = Field(None, description="키워드 관련도 (keyword 모드)")
    final_score: Optional[float] = Field(
        None, description="하이브리드 점수 (0.0~1.0, hybrid 모드)"
    )

    # hybrid 모드 전용 (세부 점수)
    vector_score: Optional[float] = Field(
        None, description="벡터 유사도 점수 (hybrid)"
    )
    keyword_score: Optional[float] = Field(
        None, description="키워드 관련도 점수 (hybrid)"
    )

    # vector 모드 전용 (include_chunks=true일 때)
    chunk_content: Optional[str] = Field(None, description="매칭된 청크 내용")
    chunk_index: Optional[int] = Field(None, description="청크 인덱스")
