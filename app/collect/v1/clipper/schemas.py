from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


# 중복 후보 스키마
class DuplicateCandidateResponse(BaseModel):
    """중복 후보 응답 스키마"""
    item_id: int
    title: str
    url: str
    similarity_score: float
    match_type: str  # "exact", "high", "medium", "low"
    created_at: datetime


# Request 스키마
class WebpageSyncRequest(BaseModel):
    """웹페이지 동기화 요청 스키마"""
    item_id: int
    user_id: int
    thumbnail: str
    title: str
    url: str
    summary: Optional[str] = None
    tags: Optional[list[str]] = None
    category: str
    memo: Optional[str] = None
    html_content: str


class SummarizeRequest(BaseModel):
    """요약 생성 요청 스키마"""
    url: str = Field(..., description="요약할 웹페이지 URL")
    html_content: str = Field(..., description="HTML 콘텐츠")
    user_id: int = Field(..., description="사용자 ID")
    board_id: Optional[UUID] = Field(None, description="보드 ID")
    model: Optional[str] = Field(None, description="사용할 AI 모델 (별칭)")
    budget_wtu: Optional[int] = Field(None, description="예산 WTU 제한")
    confidence_target: Optional[float] = Field(None, description="품질 목표 (0.0-1.0)")


class UserInteractionRequest(BaseModel):
    """사용자 상호작용 기록 요청"""
    user_id: str = Field(..., description="사용자 ID")
    content_id: int = Field(..., description="콘텐츠 ID")
    interaction_type: str = Field(..., description="상호작용 타입 (view, like, share, save)")
    context: Optional[str] = Field(None, description="상호작용 컨텍스트")


# Response 스키마
class WebpageSyncResponse(BaseModel):
    """동기화 응답 스키마"""
    success: bool
    message: str
    duplicate_candidates: Optional[List[DuplicateCandidateResponse]] = None


class SummarizeResponse(BaseModel):
    """요약 생성 응답 스키마"""
    summary: str
    tags: list[str]
    category: str
    usage: Optional[Dict] = Field(None, description="사용량 정보")
    routing: Optional[Dict] = Field(None, description="모델 라우팅 정보")
