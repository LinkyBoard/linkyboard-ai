from typing import Optional
from fastapi import APIRouter, HTTPException, File, UploadFile
from pydantic import BaseModel, HttpUrl

# Router 인스턴스 생성
router = APIRouter(
    prefix="/clipper",
    tags=["clipper"],
    responses={404: {"description": "Not found"}},
)

# Request/Response 모델 정의
class SaveOnlyRequest(BaseModel):
    """저장만 하기 요청 모델"""
    thumbnail: str  # base64 또는 URL
    title: str
    url: HttpUrl
    html_content: str

class SaveOnlyResponse(BaseModel):
    """저장만 하기 응답 모델"""
    success: bool
    message: str

class SummarizeRequest(BaseModel):
    """요약과 함께 저장하기 - 첫 번째 요청 모델"""
    url: HttpUrl
    html_content: str

class SummarizeResponse(BaseModel):
    """요약과 함께 저장하기 - 첫 번째 응답 모델"""
    summary: str
    keywords: list[str]
    category: str

class SaveWithSummaryRequest(BaseModel):
    """요약과 함께 저장하기 - 두 번째 요청 모델"""
    thumbnail: str  # base64 또는 URL
    title: str
    url: HttpUrl
    memo: Optional[str] = None
    summary: str
    keywords: list[str]
    category: str

class SaveWithSummaryResponse(BaseModel):
    """요약과 함께 저장하기 - 두 번째 응답 모델"""
    success: bool
    message: str

# API 엔드포인트 정의
@router.post("/save-only", response_model=SaveOnlyResponse)
async def save_only(request: SaveOnlyRequest):
    """
    저장만 하기
    
    클라이언트로부터 썸네일, 제목, URL, HTML 파일을 받아서 저장만 처리합니다.
    """
    try:
        # TODO: AI 서비스에 URL과 HTML 파일 전송하여 저장 처리
        # ai_response = await ai_service.save_content(request.url, request.html_content)
        
        # 현재는 스켈레톤 코드이므로 성공 응답 반환
        return SaveOnlyResponse(
            success=True,
            message="콘텐츠가 성공적으로 저장되었습니다."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"저장 중 오류가 발생했습니다: {str(e)}")

@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_content(request: SummarizeRequest):
    """
    요약과 함께 저장하기 - 1단계: 요약 생성
    
    URL과 HTML 파일을 받아서 요약, 키워드, 카테고리를 생성합니다.
    """
    try:
        # TODO: AI 서비스에 URL과 HTML 파일 전송하여 요약 생성
        # ai_response = await ai_service.generate_summary(request.url, request.html_content)
        
        # 현재는 스켈레톤 코드이므로 더미 데이터 반환
        return SummarizeResponse(
            summary="이것은 웹페이지의 요약 내용입니다.",
            keywords=["키워드1", "키워드2", "키워드3"],
            category="기술"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"요약 생성 중 오류가 발생했습니다: {str(e)}")

@router.post("/save-with-summary", response_model=SaveWithSummaryResponse)
async def save_with_summary(request: SaveWithSummaryRequest):
    """
    요약과 함께 저장하기 - 2단계: 최종 저장
    
    썸네일, 제목, URL, 메모, 요약, 키워드, 카테고리를 모두 포함하여 저장합니다.
    """
    try:
        # TODO: 모든 데이터를 포함하여 최종 저장 처리
        # save_response = await storage_service.save_complete_data(request)
        
        # 현재는 스켈레톤 코드이므로 성공 응답 반환
        return SaveWithSummaryResponse(
            success=True,
            message="요약과 함께 콘텐츠가 성공적으로 저장되었습니다."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"저장 중 오류가 발생했습니다: {str(e)}")

# 추가 유틸리티 엔드포인트
@router.get("/health")
async def health_check():
    """
    클리퍼 서비스 상태 확인
    """
    return {"status": "healthy", "service": "clipper"}