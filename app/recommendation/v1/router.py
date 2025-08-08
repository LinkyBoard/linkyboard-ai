from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from app.recommendation.v1.service import RecommendationService, get_recommendation_service
from app.recommendation.v1.schemas import (
    ContentRecommendationRequest,
    SimilarContentRequest,
    TagRecommendationRequest,
    CategoryRecommendationRequest,
    RecommendationFeedback,
    ContentRecommendationResponse,
    TagRecommendationResponse,
    CategoryRecommendationResponse
)
from app.core.logging import get_logger

logger = get_logger("recommendation_router")

router = APIRouter(prefix="/recommendation/v1", tags=["recommendation"])


@router.get("/content", response_model=ContentRecommendationResponse)
async def get_content_recommendations(
    user_id: str = Query(..., description="사용자 ID"),
    limit: int = Query(default=10, ge=1, le=50, description="추천 콘텐츠 수"),
    category_filter: Optional[str] = Query(None, description="카테고리 필터"),
    exclude_seen: bool = Query(default=True, description="이미 본 콘텐츠 제외"),
    algorithm: str = Query(default="hybrid", description="추천 알고리즘"),
    service: RecommendationService = Depends(get_recommendation_service)
):
    """사용자 맞춤 콘텐츠 추천"""
    try:
        logger.bind(user_id=user_id).info(f"Content recommendation request: limit={limit}, algorithm={algorithm}")
        
        recommendations = await service.recommend_content_for_user(
            user_id=user_id,
            limit=limit,
            category_filter=category_filter,
            exclude_seen=exclude_seen,
            algorithm=algorithm
        )
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Failed to get content recommendations for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="추천 생성 중 오류가 발생했습니다.")


@router.get("/similar/{content_id}", response_model=ContentRecommendationResponse)
async def get_similar_content(
    content_id: int,
    limit: int = Query(default=10, ge=1, le=30, description="추천 콘텐츠 수"),
    user_id: Optional[str] = Query(None, description="사용자 ID (개인화용)"),
    service: RecommendationService = Depends(get_recommendation_service)
):
    """유사 콘텐츠 추천"""
    try:
        logger.info(f"Similar content request for content_id: {content_id}")
        
        recommendations = await service.recommend_similar_content(
            content_id=content_id,
            limit=limit,
            user_id=user_id
        )
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Failed to get similar content for {content_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="유사 콘텐츠 추천 중 오류가 발생했습니다.")


# NOTE: 삭제 예정
@router.post("/tags", response_model=TagRecommendationResponse)
async def recommend_tags(
    request: TagRecommendationRequest,
    service: RecommendationService = Depends(get_recommendation_service)
):
    """태그 추천"""
    try:
        logger.bind(user_id=request.user_id).info("Tag recommendation request")
        
        recommendations = await service.recommend_tags_for_content(
            user_id=request.user_id,
            content_summary=request.content_summary,
            tag_count=request.tag_count
        )
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Failed to recommend tags for user {request.user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="태그 추천 중 오류가 발생했습니다.")


# NOTE: 삭제 예정
@router.post("/category", response_model=CategoryRecommendationResponse)
async def recommend_category(
    request: CategoryRecommendationRequest,
    service: RecommendationService = Depends(get_recommendation_service)
):
    """카테고리 추천"""
    try:
        logger.bind(user_id=request.user_id).info("Category recommendation request")
        
        recommendation = await service.recommend_category_for_content(
            user_id=request.user_id,
            content_summary=request.content_summary
        )
        
        return recommendation
        
    except Exception as e:
        logger.error(f"Failed to recommend category for user {request.user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="카테고리 추천 중 오류가 발생했습니다.")


@router.post("/feedback")
async def submit_recommendation_feedback(
    feedback: RecommendationFeedback,
    service: RecommendationService = Depends(get_recommendation_service)
):
    """추천 피드백 제출"""
    try:
        logger.bind(user_id=feedback.user_id).info(
            f"Recommendation feedback: {feedback.feedback_type} for content {feedback.content_id}"
        )
        
        await service.record_recommendation_feedback(
            user_id=feedback.user_id,
            content_id=feedback.content_id,
            feedback_type=feedback.feedback_type,
            context=feedback.context
        )
        
        return {"message": "피드백이 성공적으로 기록되었습니다."}
        
    except Exception as e:
        logger.error(f"Failed to record feedback: {str(e)}")
        raise HTTPException(status_code=500, detail="피드백 기록 중 오류가 발생했습니다.")


@router.get("/trending", response_model=ContentRecommendationResponse)
async def get_trending_content(
    limit: int = Query(default=20, ge=1, le=50, description="트렌딩 콘텐츠 수"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    time_range: str = Query(default="24h", description="시간 범위 (24h, 7d, 30d)"),
    service: RecommendationService = Depends(get_recommendation_service)
):
    """트렌딩 콘텐츠 조회"""
    try:
        logger.info(f"Trending content request: limit={limit}, category={category}, time_range={time_range}")
        
        # 시간 범위 매핑
        time_mapping = {
            "24h": 1,
            "7d": 7,
            "30d": 30
        }
        
        days = time_mapping.get(time_range, 1)
        
        # 임시로 최신 콘텐츠 반환 (실제로는 인기도 기반 구현 필요)
        recommendations = await service._get_fallback_recommendations(limit)
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Failed to get trending content: {str(e)}")
        raise HTTPException(status_code=500, detail="트렌딩 콘텐츠 조회 중 오류가 발생했습니다.")