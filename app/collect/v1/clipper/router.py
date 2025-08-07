from typing import Optional
from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from .schemas import (
    SaveOnlyResponse,
    SummarizeResponse,
    SaveWithSummaryResponse,
    SaveOnlyRequest,
    SummarizeRequest,
    SaveWithSummaryRequest
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
@router.post("/save-only", response_model=SaveOnlyResponse)
async def save_only(
    user_id: str = Form(..., description="사용자 ID"),
    thumbnail: str = Form(..., description="썸네일 이미지 (base64 또는 URL)"),
    title: str = Form(..., description="페이지 제목"),
    url: str = Form(..., description="페이지 URL"),
    html_file: UploadFile = File(..., description="HTML 파일")
):
    """
    저장만 하기
    
    클라이언트로부터 썸네일, 제목, URL, HTML 파일을 받아서 저장만 처리합니다.
    """
    try:
        # HTML 파일 내용 읽기
        html_content = await html_file.read()
        html_content_str = html_content.decode('utf-8')
        
        # 요청 데이터 생성
        request_data = SaveOnlyRequest(
            user_id=user_id,
            thumbnail=thumbnail,
            title=title,
            url=url,
            html_content=html_content_str
        )
        
        # 서비스 레이어 호출
        result = await clipper_service.save_only(request_data)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_content(
    url: str = Form(..., description="페이지 URL"),
    html_file: UploadFile = File(..., description="HTML 파일")
):
    """
    요약과 함께 저장하기 - 1단계: 요약 생성
    
    URL과 HTML 파일을 받아서 요약, 키워드, 카테고리를 생성합니다.
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
        result = await clipper_service.generate_summary(request_data)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save-with-summary", response_model=SaveWithSummaryResponse)
async def save_with_summary(
    user_id: str = Form(..., description="사용자 ID"),
    thumbnail: str = Form(..., description="썸네일 이미지 (base64 또는 URL)"),
    title: str = Form(..., description="페이지 제목"),
    url: str = Form(..., description="페이지 URL"),
    summary: str = Form(..., description="페이지 요약"),
    keywords: str = Form(..., description="키워드 (콤마로 구분)"),
    category: str = Form(..., description="카테고리"),
    memo: Optional[str] = Form(None, description="사용자 메모")
):
    """
    요약과 함께 저장하기 - 2단계: 최종 저장
    
    썸네일, 제목, URL, 메모, 요약, 키워드, 카테고리를 모두 포함하여 저장합니다.
    """
    try:
        # 키워드 문자열을 리스트로 변환
        keywords_list = [keyword.strip() for keyword in keywords.split(',') if keyword.strip()]
        
        # 요청 데이터 생성
        request_data = SaveWithSummaryRequest(
            user_id=user_id,
            thumbnail=thumbnail,
            title=title,
            url=url,
            memo=memo,
            summary=summary,
            keywords=keywords_list,
            category=category
        )
        
        # 서비스 레이어 호출
        result = await clipper_service.save_with_summary(request_data)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
