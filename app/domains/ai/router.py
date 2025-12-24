"""ai 도메인 라우터

AI 도메인 관련 API 엔드포인트입니다.
"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import verify_internal_api_key
from app.core.schemas import (
    APIResponse,
    ListAPIResponse,
    create_list_response,
    create_response,
)
from app.domains.ai.repository import AIRepository
from app.domains.ai.schemas import (
    FallbackFlow,
    FallbackFlowsResponse,
    ModelHealthResponse,
    ModelHealthStats,
    SearchRequest,
    SearchResultResponse,
    SummarizeResponse,
    TierHealthResponse,
    TierHealthStats,
)
from app.domains.ai.search.service import AISearchService
from app.domains.ai.summarization.service import SummarizationService

router = APIRouter()


def get_summarization_service(
    session: AsyncSession = Depends(get_db),
) -> SummarizationService:
    """SummarizationService 의존성"""
    return SummarizationService(session)


def get_search_service(
    session: AsyncSession = Depends(get_db),
) -> AISearchService:
    """SearchService 의존성"""
    return AISearchService(session)


@router.post(
    "/summarize/webpage",
    response_model=APIResponse[SummarizeResponse],
    dependencies=[Depends(verify_internal_api_key)],
)
async def summarize_webpage(
    url: str = Form(...),
    user_id: int = Form(...),
    html_file: Optional[UploadFile] = File(None),
    tag_count: int = Form(5),
    refresh: bool = Form(False),
    summarization_service: SummarizationService = Depends(
        get_summarization_service
    ),
):
    """웹페이지 요약 생성

    Args:
        url: 웹페이지 URL
        user_id: 사용자 ID
        html_file: HTML 파일 (옵션). 제공되지 않으면 URL에서 직접 가져옴
        tag_count: 태그 개수
        refresh: 캐시 갱신 여부
    """
    html_str = None
    if html_file:
        # HTML 파일이 제공된 경우
        html_content = await html_file.read()
        html_str = html_content.decode("utf-8")

    result = await summarization_service.summarize_webpage(
        url=url,
        html_content=html_str,
        user_id=user_id,
        tag_count=tag_count,
        refresh=refresh,
    )

    return create_response(
        data=SummarizeResponse(**result), message="요약이 생성되었습니다."
    )


@router.post(
    "/summarize/youtube",
    response_model=APIResponse[SummarizeResponse],
    dependencies=[Depends(verify_internal_api_key)],
)
async def summarize_youtube(
    url: str = Form(..., description="YouTube URL"),
    user_id: int = Form(..., description="사용자 ID"),
    subtitle_file: Optional[UploadFile] = File(
        None, description="자막 파일 (SRT, VTT 등). 미제공 시 enable_stt 필요"
    ),
    tag_count: int = Form(5, ge=1, le=20, description="추천 태그 수"),
    refresh: bool = Form(False, description="캐시 무시하고 재생성"),
    enable_stt: bool = Form(False, description="STT 활성화 (준비 중)"),
    summarization_service: SummarizationService = Depends(
        get_summarization_service
    ),
):
    """유튜브 요약 생성

    Args:
        url: YouTube URL
        user_id: 사용자 ID
        subtitle_file: 자막 파일 (옵션). SRT, VTT 등의 자막 파일
        tag_count: 추천 태그 수
        refresh: 캐시 무시하고 재생성 여부
        enable_stt: STT 활성화 여부 (아직 준비 중)
    """
    subtitle_str = None
    if subtitle_file:
        # 자막 파일이 제공된 경우
        subtitle_content = await subtitle_file.read()
        subtitle_str = subtitle_content.decode("utf-8")

    result = await summarization_service.summarize_youtube(
        url=url,
        subtitle_content=subtitle_str,
        user_id=user_id,
        tag_count=tag_count,
        refresh=refresh,
        enable_stt=enable_stt,
    )

    return create_response(
        data=SummarizeResponse(**result), message="요약이 생성되었습니다."
    )


@router.post(
    "/summarize/pdf",
    response_model=APIResponse[SummarizeResponse],
    dependencies=[Depends(verify_internal_api_key)],
)
async def summarize_pdf(
    user_id: int = Form(...),
    pdf_file: UploadFile = File(...),
    tag_count: int = Form(5),
    refresh: bool = Form(False),
    summarization_service: SummarizationService = Depends(
        get_summarization_service
    ),
):
    """PDF 요약 생성"""
    pdf_content = await pdf_file.read()

    result = await summarization_service.summarize_pdf(
        pdf_content=pdf_content,
        user_id=user_id,
        tag_count=tag_count,
        refresh=refresh,
    )

    return create_response(
        data=SummarizeResponse(**result), message="요약이 생성되었습니다."
    )


@router.post(
    "/search",
    response_model=ListAPIResponse[SearchResultResponse],
    dependencies=[Depends(verify_internal_api_key)],
)
async def search_contents(
    request: SearchRequest,
    service: AISearchService = Depends(get_search_service),
):
    """콘텐츠 검색"""
    results, total = await service.search(
        query=request.query,
        user_id=request.user_id,
        mode=request.search_mode,
        filters=request.filters,
        page=request.page,
        size=request.size,
        threshold=request.threshold,
        include_chunks=request.include_chunks,
    )

    # dict → SearchResultResponse 변환
    response_results = [SearchResultResponse(**r) for r in results]

    return create_list_response(
        data=response_results,
        total=total,
        page=request.page,
        size=request.size,
    )


# 모델 헬스 모니터링 API


@router.get(
    "/health/model",
    response_model=ModelHealthResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def get_model_health(
    model_alias: Optional[str] = None,
    hours: int = 24,
    session: AsyncSession = Depends(get_db),
) -> ModelHealthResponse:
    """모델 헬스 통계 조회

    Args:
        model_alias: 특정 모델 별칭 (None이면 전체)
        hours: 조회 시간 범위 (기본 24시간)
        session: DB 세션

    Returns:
        ModelHealthResponse: 모델 헬스 통계

    Example::

        # 특정 모델 조회
        GET /api/v1/ai/health/model?model_alias=claude-4.5-haiku&hours=24

        # 전체 모델 조회
        GET /api/v1/ai/health/model?hours=48
    """
    repo = AIRepository(session)
    stats = await repo.get_model_health_stats(
        model_alias=model_alias, hours=hours
    )

    return ModelHealthResponse(
        success=True,
        data=ModelHealthStats(model_alias=model_alias, **stats),
    )


@router.get(
    "/health/tier/{tier}",
    response_model=TierHealthResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def get_tier_health(
    tier: str,
    hours: int = 24,
    session: AsyncSession = Depends(get_db),
) -> TierHealthResponse:
    """티어별 헬스 통계 조회

    Args:
        tier: LLM 티어 (light, standard, premium, search, embedding)
        hours: 조회 시간 범위 (기본 24시간)
        session: DB 세션

    Returns:
        TierHealthResponse: 티어 헬스 통계

    Example::

        GET /api/v1/ai/health/tier/light?hours=24
    """
    repo = AIRepository(session)
    stats = await repo.get_tier_health_stats(tier=tier, hours=hours)

    return TierHealthResponse(success=True, data=TierHealthStats(**stats))


@router.get(
    "/health/fallback-flows",
    response_model=FallbackFlowsResponse,
    dependencies=[Depends(verify_internal_api_key)],
)
async def get_fallback_flows(
    hours: int = 24,
    session: AsyncSession = Depends(get_db),
) -> FallbackFlowsResponse:
    """Fallback 흐름 조회

    Args:
        hours: 조회 시간 범위 (기본 24시간)
        session: DB 세션

    Returns:
        FallbackFlowsResponse: Fallback 흐름 리스트

    Example::

        GET /api/v1/ai/health/fallback-flows?hours=24

        Response:
        {
            "success": true,
            "data": [
                {
                    "source_model": "claude-4.5-haiku",
                    "fallback_to": "gemini-2.0-flash",
                    "count": 15,
                    "error_types": {
                        "InsufficientCredits": 10,
                        "RateLimitError": 5
                    }
                },
                ...
            ]
        }
    """
    repo = AIRepository(session)
    flows = await repo.get_fallback_flows(hours=hours)

    # dict → FallbackFlow 변환
    flow_objects = [FallbackFlow(**flow) for flow in flows]

    return FallbackFlowsResponse(success=True, data=flow_objects)
