from typing import Optional, List, Dict
from pydantic import BaseModel, Field


# Request 스키마
class WebpageSyncRequest(BaseModel):
    """웹페이지 동기화 요청 스키마"""
    item_id: int
    user_id: int
    thumbnail: str
    title: str
    url: str
    summary: Optional[str] = None
    keywords: Optional[list[str]] = None
    category: str
    memo: Optional[str] = None
    html_content: str


class SummarizeRequest(BaseModel):
    """요약 생성 요청 스키마"""
    url: str
    html_content: str


class SummarizeWithRecommendationsRequest(BaseModel):
    """추천 기능이 포함된 요약 요청"""
    url: str = Field(..., description="요약할 웹페이지 URL")
    html_content: str = Field(..., description="HTML 콘텐츠")
    user_id: int = Field(..., description="사용자 ID")
    tag_count: int = Field(default=5, ge=1, le=10, description="추천 태그 수")
    auto_save: bool = Field(default=False, description="자동 저장 여부")
    item_id: Optional[int] = Field(None, description="아이템 ID (저장 시 필요)")
    title: Optional[str] = Field(None, description="페이지 제목")


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


class SummarizeResponse(BaseModel):
    """요약 생성 응답 스키마"""
    summary: str
    tags: list[str]
    category: str


class RecommendationData(BaseModel):
    """추천 데이터"""
    recommended_tags: List[str] = Field(..., description="추천된 태그들")
    recommended_category: str = Field(..., description="추천된 카테고리")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="추천 신뢰도")
    user_history_tags: List[str] = Field(..., description="사용자 이력 태그들")
    ai_generated_tags: List[str] = Field(..., description="AI 생성 태그들")
    similar_categories: List[str] = Field(..., description="유사 카테고리들")
    user_preferred_categories: List[str] = Field(..., description="사용자 선호 카테고리들")


class SummarizeWithRecommendationsResponse(BaseModel):
    """추천 기능이 포함된 요약 응답"""
    summary_id: Optional[int] = Field(None, description="요약 ID (저장된 경우)")
    summary: str = Field(..., description="요약 내용")
    url: str = Field(..., description="원본 URL")
    recommendations: RecommendationData = Field(..., description="추천 데이터")
    processing_time: float = Field(..., description="처리 시간 (초)")
    saved: bool = Field(..., description="저장 여부")
