"""Contents 도메인 라우터

콘텐츠 동기화 및 관리 API 엔드포인트입니다.
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
from app.core.utils.pagination import PageParams
from app.domains.contents.schemas import (
    ContentDeleteRequest,
    ContentDeleteResponse,
    ContentListRequest,
    ContentResponse,
    ContentSyncResponse,
    PDFSyncRequest,
    WebpageSyncRequest,
    YouTubeSyncRequest,
)
from app.domains.contents.service import ContentService

router = APIRouter()


def get_content_service(
    session: AsyncSession = Depends(get_db),
) -> ContentService:
    """ContentService 의존성"""
    return ContentService(session)


@router.post(
    "/webpage/sync",
    response_model=APIResponse[ContentSyncResponse],
    status_code=201,
    dependencies=[Depends(verify_internal_api_key)],
)
async def sync_webpage(
    data: WebpageSyncRequest,
    service: ContentService = Depends(get_content_service),
):
    """웹페이지 콘텐츠 동기화"""
    content = await service.sync_webpage(data)
    return create_response(
        data=ContentSyncResponse(content_id=content.id, file_hash=None),
        message="웹페이지 콘텐츠가 동기화되었습니다.",
    )


@router.post(
    "/youtube/sync",
    response_model=APIResponse[ContentSyncResponse],
    status_code=201,
    dependencies=[Depends(verify_internal_api_key)],
)
async def sync_youtube(
    data: YouTubeSyncRequest,
    service: ContentService = Depends(get_content_service),
):
    """YouTube 콘텐츠 동기화"""
    content = await service.sync_youtube(data)
    return create_response(
        data=ContentSyncResponse(content_id=content.id, file_hash=None),
        message="YouTube 콘텐츠가 동기화되었습니다.",
    )


@router.post(
    "/pdf/sync",
    response_model=APIResponse[ContentSyncResponse],
    status_code=201,
    dependencies=[Depends(verify_internal_api_key)],
)
async def sync_pdf(
    content_id: int = Form(..., gt=0, description="Spring Boot 콘텐츠 ID"),
    user_id: int = Form(..., gt=0, description="사용자 ID"),
    title: str = Form(..., min_length=1, max_length=500, description="제목"),
    file: UploadFile = File(..., description="PDF 파일"),
    summary: str | None = Form(None, description="요약"),
    tags: str | None = Form(None, description="태그 (쉼표 구분)"),
    category: str | None = Form(None, max_length=100, description="카테고리"),
    memo: str | None = Form(None, description="사용자 메모"),
    service: ContentService = Depends(get_content_service),
):
    """PDF 콘텐츠 동기화"""
    # 파일 내용 읽기
    file_content = await file.read()

    # tags 파싱 (쉼표 구분 문자열 → 리스트)
    tags_list = None
    if tags:
        tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

    # PDFSyncRequest 생성
    pdf_data = PDFSyncRequest(
        content_id=content_id,
        user_id=user_id,
        title=title,
        summary=summary,
        tags=tags_list,
        category=category,
        memo=memo,
    )

    # 서비스 호출
    content, file_hash = await service.sync_pdf(pdf_data, file_content)

    return create_response(
        data=ContentSyncResponse(
            content_id=content.id,
            file_hash=file_hash,
        ),
        message="PDF 콘텐츠가 동기화되었습니다.",
    )


@router.get(
    "/{content_id}",
    response_model=APIResponse[ContentResponse],
    dependencies=[Depends(verify_internal_api_key)],
)
async def get_content(
    content_id: int,
    user_id: int,
    service: ContentService = Depends(get_content_service),
):
    """콘텐츠 상세 조회"""
    content = await service.get_content(content_id, user_id)
    return create_response(
        data=ContentResponse.model_validate(content),
        message="콘텐츠 정보를 조회했습니다.",
    )


@router.delete(
    "/",
    response_model=APIResponse[ContentDeleteResponse],
    status_code=200,
    dependencies=[Depends(verify_internal_api_key)],
)
async def delete_contents(
    data: ContentDeleteRequest,
    service: ContentService = Depends(get_content_service),
):
    """콘텐츠 벌크 삭제"""
    result = await service.delete_contents(data.content_ids, data.user_id)
    return create_response(
        data=result,
        message=f"{result.deleted_count}개의 콘텐츠가 삭제되었습니다.",
    )


@router.get(
    "/",
    response_model=ListAPIResponse[ContentResponse],
    dependencies=[Depends(verify_internal_api_key)],
)
async def list_contents(
    page_params: PageParams = Depends(),
    user_id: int | None = None,
    filters: ContentListRequest = Depends(),
    service: ContentService = Depends(get_content_service),
):
    """콘텐츠 목록 조회"""
    if user_id is None:
        raise ValueError("user_id는 필수 파라미터입니다.")

    contents, total = await service.list_contents(
        user_id=user_id,
        page=page_params.page,
        size=page_params.size,
        filters=filters,
    )

    return create_list_response(
        data=[ContentResponse.model_validate(content) for content in contents],
        total=total,
        page=page_params.page,
        size=page_params.size,
        message="콘텐츠 목록을 조회했습니다.",
    )
