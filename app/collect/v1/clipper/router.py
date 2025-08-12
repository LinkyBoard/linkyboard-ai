from typing import Optional
import time
from fastapi import APIRouter, BackgroundTasks, HTTPException, File, UploadFile, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.logging import get_logger
from .schemas import (
    WebpageSyncRequest,
    SummarizeResponse,
    WebpageSyncResponse,
    SummarizeRequest,
    SummarizeWithRecommendationsRequest,
    SummarizeWithRecommendationsResponse,
    UserInteractionRequest,
    RecommendationData,
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
    keywords: Optional[list[str]] = Form(None, description="키워드 목록"),
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
            keywords=keywords or [],
            category=category,
            memo=memo,
            html_content=html_content_str
        )

        # 서비스 레이어 호출
        result = await clipper_service.sync_webpage(session, background_tasks, request_data)
        logger.info(f"Webpage sync completed successfully for item {item_id}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to sync webpage for item {item_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webpage/summarize", response_model=SummarizeResponse)
async def summarize_webpage(
    url: str = Form(..., description="페이지 URL"),
    html_file: UploadFile = File(..., description="HTML 파일")
):
    """
    웹페이지 요약 생성
    
    클라이언트로부터 페이지 URL과 HTML 파일을 받아서 요약, 키워드, 카테고리를 생성합니다.
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
            html_content=html_content_str
        )
        
        # 서비스 레이어 호출
        result = await clipper_service.generate_webpage_summary(request_data)
        logger.info(f"Summarize completed successfully for URL: {url}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to summarize webpage: {str(e)}")
        raise HTTPException(status_code=500, detail=f"요약 생성 중 오류가 발생했습니다: {str(e)}")


@router.post("/summarize-with-recommendations", response_model=SummarizeWithRecommendationsResponse)
async def summarize_with_recommendations(
    request: SummarizeWithRecommendationsRequest,
    session: AsyncSession = Depends(get_db),
    clipper_service = Depends(get_clipper_service)
):
    """웹페이지 요약 + 사용자 맞춤 태그/카테고리 추천"""
    try:
        start_time = time.time()
        
        logger.bind(user_id=request.user_id).info(f"Summarizing with recommendations: {request.url}")
        
        # 1. 요약 및 추천 생성
        summary_request = SummarizeRequest(
            url=request.url,
            html_content=request.html_content
        )
        
        result = await clipper_service.generate_webpage_summary_with_recommendations(
            session=session,
            request_data=summary_request,
            user_id=request.user_id,
            tag_count=request.tag_count
        )
        
        # 2. 자동 저장 처리
        summary_id = None
        saved = False
        if request.auto_save and request.item_id and request.title:
            summary_id = await clipper_service.save_content_with_recommendations(
                session=session,
                user_id=request.user_id,
                item_id=request.item_id,
                title=request.title,
                summary=result['summary'],
                url=request.url,
                recommended_tags=result['recommended_tags'],
                recommended_category=result['recommended_category'],
                html_content=request.html_content
            )
            saved = True
        
        processing_time = time.time() - start_time
        
        # 3. 응답 구성
        response = SummarizeWithRecommendationsResponse(
            summary_id=summary_id,
            summary=result['summary'],
            url=request.url,
            recommendations=RecommendationData(
                recommended_tags=result['recommended_tags'],
                recommended_category=result['recommended_category'],
                confidence_score=result['confidence_score'],
                user_history_tags=result['user_history_tags'],
                ai_generated_tags=result['ai_generated_tags'],
                similar_categories=result['similar_categories'],
                user_preferred_categories=result['user_preferred_categories']
            ),
            processing_time=processing_time,
            saved=saved
        )
        
        logger.bind(user_id=request.user_id).info(f"Successfully processed with recommendations in {processing_time:.2f}s")
        return response
        
    except Exception as e:
        logger.error(f"Failed to summarize with recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail="요약 및 추천 생성 중 오류가 발생했습니다.")


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

