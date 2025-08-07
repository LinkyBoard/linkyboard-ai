from typing import Optional
from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from .schemas import (
    WebpageSyncRequest,
    SummarizeResponse,
    WebpageSyncResponse,
    SummarizeRequest,
)
from .service import clipper_service

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
        # HTML 파일 내용 읽기
        html_content = await html_file.read()
        html_content_str = html_content.decode('utf-8')
        
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
        result = await clipper_service.sync_webpage(session, request_data)
        return result
        
    except Exception as e:
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
        # HTML 파일 내용 읽기
        html_content = await html_file.read()
        html_content_str = html_content.decode('utf-8')
        
        # 요청 데이터 생성
        request_data = SummarizeRequest(
            url=url,
            html_content=html_content_str
        )
        
        # 서비스 레이어 호출
        result = await clipper_service.generate_webpage_summary(request_data)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

