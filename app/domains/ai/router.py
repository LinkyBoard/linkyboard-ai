"""ai 도메인 라우터

AI 도메인 관련 API 엔드포인트입니다.
"""

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
from app.domains.ai.schemas import (
    SearchRequest,
    SearchResultResponse,
    SummarizeResponse,
    YoutubeSummarizeRequest,
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
    html_file: UploadFile = File(...),
    tag_count: int = Form(5),
    refresh: bool = Form(False),
    summarization_service: SummarizationService = Depends(
        get_summarization_service
    ),
):
    """웹페이지 요약 생성"""
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
    request: YoutubeSummarizeRequest,
    summarization_service: SummarizationService = Depends(
        get_summarization_service
    ),
):
    """유튜브 요약 생성"""

    result = await summarization_service.summarize_youtube(
        url=request.url,
        user_id=request.user_id,
        tag_count=request.tag_count,
        refresh=request.refresh,
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
