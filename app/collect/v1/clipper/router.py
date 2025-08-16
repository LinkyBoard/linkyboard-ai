from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, File, UploadFile, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.logging import get_logger
from .schemas import (
    WebpageSyncRequest,
    SummarizeResponse,
    WebpageSyncResponse,
    SummarizeRequest,
    UserInteractionRequest,
)
from .service import clipper_service, get_clipper_service

logger = get_logger(__name__)

# Router 인스턴스 생성
router = APIRouter(
    prefix="/api/v1/clipper",
    tags=["clipper"],
    responses={
        400: {"description": "Bad Request"},
        404: {"description": "Not found"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)

# API 엔드포인트 정의
@router.post("/webpage/sync", response_model=WebpageSyncResponse)
async def sync_webpage(
    background_tasks: BackgroundTasks,
    item_id: int = Form(..., description="Item ID"),
    user_id: int = Form(..., description="사용자 ID"),
    thumbnail: str = Form(..., description="썸네일 이미지 (URL)"),
    title: str = Form(..., description="페이지 제목"),
    url: str = Form(..., description="페이지 URL"),
    summary: Optional[str] = Form(None, description="페이지 요약"),
    tags: Optional[list[str]] = Form(None, description="태그 목록"),
    category: str = Form(..., description="카테고리"),
    memo: Optional[str] = Form(None, description="사용자 메모"),
    html_file: UploadFile = File(..., description="HTML 파일"),
    session: AsyncSession = Depends(get_db)  # 의존성 주입으로 세션 관리
):
    """
    webpage 저장
    
    클라이언트로부터 webpage의 썸네일, 제목, URL, HTML 파일을 받아서 저장만 처리합니다.
    """
    try:
        logger.info(f"Received webpage sync request for item {item_id}, user {user_id}")
        
        # HTML 파일 내용 읽기
        html_content = await html_file.read()
        html_content_str = html_content.decode('utf-8')
        logger.info(f"HTML content size: {len(html_content_str)} characters")
        
        # 요청 데이터 생성
        request_data = WebpageSyncRequest(
            item_id=item_id,
            user_id=user_id,
            thumbnail=thumbnail,
            title=title,
            url=url,
            summary=summary,
            tags=tags or [],
            category=category,
            memo=memo,
            html_content=html_content_str
        )

        # 서비스 레이어 호출
        await clipper_service.sync_webpage(session, background_tasks, request_data)
        logger.info(f"Webpage sync completed successfully for item {item_id}")
        
        # 성공 응답 반환
        return WebpageSyncResponse(
            success=True,
            message="웹페이지가 성공적으로 동기화되었습니다."
        )
        
    except Exception as e:
        logger.error(f"Failed to sync webpage for item {item_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webpage/summarize", response_model=SummarizeResponse)
async def summarize_webpage(
    url: str = Form(..., description="페이지 URL"),
    html_file: UploadFile = File(..., description="HTML 파일"),
    user_id: int = Form(..., description="사용자 ID"),
    tag_count: int = Form(default=5, description="추천 태그 수"),
    session: AsyncSession = Depends(get_db),
    clipper_service = Depends(get_clipper_service)
):
    """
    웹페이지 요약 생성 (사용자 맞춤 추천 포함)
    
    사용자 ID에 맞춰 개인화된 태그/카테고리 추천을 포함하여 요약을 생성합니다.
    """
    try:
        logger.info(f"Received summarize request for URL: {url}")
        
        # HTML 파일 내용 읽기
        html_content = await html_file.read()
        html_content_str = html_content.decode('utf-8')
        logger.info(f"HTML content size: {len(html_content_str)} characters")
        
        # 요청 데이터 생성
        request_data = SummarizeRequest(
            url=url,
            html_content=html_content_str,
            user_id=user_id
        )
        
        # 개인화된 요약 및 추천 생성
        logger.bind(user_id=user_id).info(f"Generating personalized summary for user {user_id}")
        
        result = await clipper_service.generate_webpage_summary_with_recommendations(
            session=session,
            request_data=request_data,
            user_id=user_id,
            tag_count=tag_count
        )
        
        # SummarizeResponse 형식으로 응답 구성
        return SummarizeResponse(
            summary=result['summary'],
            tags=result['recommended_tags'],
            category=result['recommended_category']
        )
        
    except Exception as e:
        logger.error(f"Failed to summarize webpage: {str(e)}")
        raise HTTPException(status_code=500, detail=f"요약 생성 중 오류가 발생했습니다: {str(e)}")


@router.post("/interaction")
async def record_user_interaction(
    request: UserInteractionRequest,
    session: AsyncSession = Depends(get_db),
    clipper_service = Depends(get_clipper_service)
):
    """사용자 콘텐츠 상호작용 기록"""
    try:
        logger.bind(user_id=request.user_id).info(
            f"Recording interaction: {request.interaction_type} for content {request.content_id}"
        )
        
        await clipper_service.record_user_content_interaction(
            session=session,
            user_id=request.user_id,
            content_id=request.content_id,
            interaction_type=request.interaction_type
        )
        
        return {"message": "상호작용이 성공적으로 기록되었습니다."}
        
    except Exception as e:
        logger.error(f"Failed to record user interaction: {str(e)}")
        raise HTTPException(status_code=500, detail="상호작용 기록 중 오류가 발생했습니다.")

