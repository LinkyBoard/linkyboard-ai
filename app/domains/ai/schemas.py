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


class UsageInfo(BaseModel):
    """AI 사용량 정보"""

    total_input_tokens: int = Field(..., description="총 입력 토큰")
    total_output_tokens: int = Field(..., description="총 출력 토큰")
    total_wtu: int = Field(..., description="총 WTU (Weighted Token Unit)")


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
    usage: UsageInfo = Field(..., description="토큰 사용량 정보")


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


# 모델 헬스 모니터링 스키마


class ModelHealthStats(BaseModel):
    """모델 헬스 통계"""

    model_alias: Optional[str] = Field(
        None, description="모델 별칭 (전체 조회 시 None)"
    )
    total_calls: int = Field(..., description="총 호출 횟수")
    success_count: int = Field(..., description="성공 횟수")
    failed_count: int = Field(..., description="실패 횟수")
    fallback_count: int = Field(..., description="Fallback 발생 횟수")
    success_rate: float = Field(..., description="성공률 (%)")
    avg_response_time_ms: float = Field(..., description="평균 응답 시간 (밀리초)")
    error_breakdown: dict[str, int] = Field(..., description="에러 타입별 발생 횟수")


class TierModelStats(BaseModel):
    """티어 내 모델별 통계"""

    alias: str = Field(..., description="모델 별칭")
    total_calls: int = Field(..., description="총 호출 횟수")
    success_rate: float = Field(..., description="성공률 (%)")
    avg_response_time_ms: float = Field(..., description="평균 응답 시간 (밀리초)")


class TierHealthStats(BaseModel):
    """티어 헬스 통계"""

    tier: str = Field(..., description="LLM 티어")
    models: list[TierModelStats] = Field(..., description="티어 내 모델 통계")


class FallbackFlow(BaseModel):
    """Fallback 흐름"""

    source_model: str = Field(..., description="원본 모델 별칭")
    fallback_to: str = Field(..., description="Fallback된 모델 별칭")
    count: int = Field(..., description="Fallback 발생 횟수")
    error_types: dict[str, int] = Field(..., description="에러 타입별 발생 횟수")


class ModelHealthResponse(BaseModel):
    """모델 헬스 조회 응답"""

    success: bool = Field(True, description="성공 여부")
    data: ModelHealthStats = Field(..., description="헬스 통계 데이터")


class TierHealthResponse(BaseModel):
    """티어 헬스 조회 응답"""

    success: bool = Field(True, description="성공 여부")
    data: TierHealthStats = Field(..., description="티어 헬스 통계 데이터")


class FallbackFlowsResponse(BaseModel):
    """Fallback 흐름 조회 응답"""

    success: bool = Field(True, description="성공 여부")
    data: list[FallbackFlow] = Field(..., description="Fallback 흐름 리스트")
