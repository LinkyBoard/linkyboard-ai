from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ContentRecommendationRequest(BaseModel):
    """콘텐츠 추천 요청"""
    user_id: str = Field(..., description="사용자 ID")
    limit: int = Field(default=10, ge=1, le=50, description="추천 콘텐츠 수")
    category_filter: Optional[str] = Field(None, description="카테고리 필터")
    exclude_seen: bool = Field(default=True, description="이미 본 콘텐츠 제외")
    algorithm: str = Field(default="hybrid", description="추천 알고리즘 타입")


class SimilarContentRequest(BaseModel):
    """유사 콘텐츠 추천 요청"""
    content_id: int = Field(..., description="기준 콘텐츠 ID")
    limit: int = Field(default=10, ge=1, le=30, description="추천 콘텐츠 수")
    user_id: Optional[str] = Field(None, description="사용자 ID (개인화용)")


class TagRecommendationRequest(BaseModel):
    """태그 추천 요청"""
    user_id: str = Field(..., description="사용자 ID")
    content_summary: str = Field(..., description="콘텐츠 요약")
    tag_count: int = Field(default=5, ge=1, le=10, description="추천 태그 수")


class CategoryRecommendationRequest(BaseModel):
    """카테고리 추천 요청"""
    user_id: str = Field(..., description="사용자 ID")
    content_summary: str = Field(..., description="콘텐츠 요약")


class RecommendationFeedback(BaseModel):
    """추천 피드백"""
    user_id: str = Field(..., description="사용자 ID")
    content_id: int = Field(..., description="콘텐츠 ID")
    feedback_type: str = Field(..., description="피드백 타입 (like, dislike, save, share, click)")
    context: Optional[str] = Field(None, description="추천 컨텍스트")


class RecommendedContent(BaseModel):
    """추천된 콘텐츠"""
    content_id: int
    title: str
    summary: Optional[str]
    url: str
    category: str
    keywords: List[str]
    similarity_score: float
    recommendation_reason: str
    created_at: datetime


class TagRecommendationResponse(BaseModel):
    """태그 추천 응답"""
    recommended_tags: List[str] = Field(..., description="추천된 태그들")
    user_history_tags: List[str] = Field(..., description="사용자 이력 기반 태그들")
    ai_generated_tags: List[str] = Field(..., description="AI 생성 태그들")


class CategoryRecommendationResponse(BaseModel):
    """카테고리 추천 응답"""
    recommended_category: str = Field(..., description="추천된 카테고리")
    similar_categories: List[str] = Field(..., description="유사 카테고리들")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="추천 신뢰도")


class ContentRecommendationResponse(BaseModel):
    """콘텐츠 추천 응답"""
    recommendations: List[RecommendedContent] = Field(..., description="추천 콘텐츠 목록")
    total_count: int = Field(..., description="전체 추천 수")
    algorithm_used: str = Field(..., description="사용된 알고리즘")
    user_preferences: Optional[Dict[str, Any]] = Field(None, description="사용자 선호도 정보")


class RecommendationMetrics(BaseModel):
    """추천 성능 메트릭"""
    user_id: str
    total_recommendations: int
    click_through_rate: float
    engagement_rate: float
    diversity_score: float
    avg_similarity_score: float