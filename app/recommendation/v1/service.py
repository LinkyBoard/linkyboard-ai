from fastapi import Depends
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import text
from app.core.logging import get_logger
from app.core.database import get_db
from app.ai.recommendation.vector_service import VectorProcessingService
from app.ai.recommendation.user_profiling import UserProfilingService
from app.ai.recommendation.content_scoring import ContentScoringService
from app.ai.classification.tag_extractor import TagExtractionService
from app.ai.classification.category_classifier import CategoryClassificationService
from .schemas import (
    RecommendedContent, 
    ContentRecommendationResponse
)

logger = get_logger(__name__)


class RecommendationService:
    """추천 서비스 - 모든 추천 기능을 통합 관리"""
    
    def __init__(self, db_connection):
        self.db = db_connection
        self.vector_service = VectorProcessingService(db_connection)
        self.user_profiling = UserProfilingService(db_connection)
        self.content_scoring = ContentScoringService(db_connection)
        self.tag_extractor = TagExtractionService()
        self.category_classifier = CategoryClassificationService()
        logger.info("Recommendation service initialized")
    
    async def recommend_content_for_user(
        self, 
        user_id: str, 
        limit: int = 10,
        category_filter: Optional[str] = None,
        exclude_seen: bool = True,
        algorithm: str = "hybrid"
    ) -> ContentRecommendationResponse:
        """사용자 맞춤 콘텐츠 추천"""
        try:
            logger.bind(user_id=user_id).info(f"Generating content recommendations with {algorithm} algorithm")
            
            # 1. 사용자 선호도 벡터 생성
            user_vector = await self.user_profiling.get_user_preference_vector(user_id)
            
            # 2. 후보 콘텐츠 조회
            candidate_content_ids = await self._get_candidate_content_ids(
                user_id, category_filter, exclude_seen, limit * 3  # 필터링을 위해 더 많이 조회
            )
            
            if not candidate_content_ids:
                return await self._get_fallback_recommendations(limit)
            
            # 3. 콘텐츠 점수 계산
            scored_content = await self.content_scoring.score_content_batch_for_user(
                user_id, candidate_content_ids, user_vector
            )
            
            # 4. 상위 N개 선택
            top_content = scored_content[:limit]
            
            # 5. 상세 정보 조회 및 응답 구성
            recommendations = await self._build_recommendation_response(
                top_content, algorithm, user_id
            )
            
            # 6. 사용자 선호도 정보 추가
            user_preferences = await self._get_user_preference_summary(user_id)
            
            logger.bind(user_id=user_id).info(f"Generated {len(recommendations)} recommendations")
            
            return ContentRecommendationResponse(
                recommendations=recommendations,
                total_count=len(recommendations),
                algorithm_used=algorithm,
                user_preferences=user_preferences
            )
            
        except Exception as e:
            logger.error(f"Failed to recommend content for user {user_id}: {str(e)}")
            return await self._get_fallback_recommendations(limit)
    
    async def recommend_similar_content(
        self, 
        content_id: int, 
        limit: int = 10,
        user_id: Optional[str] = None
    ) -> ContentRecommendationResponse:
        """유사 콘텐츠 추천"""
        try:
            logger.info(f"Finding similar content for content_id: {content_id}")
            
            # 1. 기준 콘텐츠의 임베딩 조회
            base_content_embedding = await self.db.fetch_one("""
                SELECT embedding FROM content_embeddings WHERE content_id = $1
            """, content_id)
            
            if not base_content_embedding:
                # 임베딩이 없다면 생성
                await self.vector_service.generate_content_embedding(content_id)
                base_content_embedding = await self.db.fetch_one("""
                    SELECT embedding FROM content_embeddings WHERE content_id = $1
                """, content_id)
            
            if not base_content_embedding:
                return ContentRecommendationResponse(
                    recommendations=[],
                    total_count=0,
                    algorithm_used="similarity",
                    user_preferences=None
                )
            
            # 2. 벡터 유사도 검색
            result = await self.db.execute(text("""
                SELECT 
                    ce.content_id,
                    s.title,
                    s.summary,
                    s.url,
                    c.name as category,
                    1 - (ce.embedding <=> :embedding::vector) as similarity_score
                FROM content_embeddings ce
                JOIN summaries s ON ce.content_id = s.id
                JOIN categories c ON s.category_id = c.id
                WHERE ce.content_id != :content_id
                AND ce.embedding <=> :embedding::vector < 0.5  -- 유사도 임계값
                ORDER BY ce.embedding <=> :embedding::vector
                LIMIT :limit
            """), {
                'embedding': base_content_embedding['embedding'], 
                'content_id': content_id, 
                'limit': limit
            })
            similar_content = result.fetchall()
            
            # 3. 응답 구성
            recommendations = []
            for row in similar_content:
                # 키워드 조회
                keywords = await self._get_content_keywords(row['content_id'])
                
                recommendation = RecommendedContent(
                    content_id=row['content_id'],
                    title=row['title'],
                    summary=row['summary'],
                    url=row['url'],
                    category=row['category'],
                    keywords=keywords,
                    similarity_score=row['similarity_score'],
                    recommendation_reason="벡터 유사도 기반",
                    created_at=datetime.utcnow()  # TODO: 실제 생성일 사용
                )
                recommendations.append(recommendation)
            
            logger.info(f"Found {len(recommendations)} similar contents")
            
            return ContentRecommendationResponse(
                recommendations=recommendations,
                total_count=len(recommendations),
                algorithm_used="similarity",
                user_preferences=None
            )
            
        except Exception as e:
            logger.error(f"Failed to find similar content for {content_id}: {str(e)}")
            return ContentRecommendationResponse(
                recommendations=[],
                total_count=0,
                algorithm_used="similarity",
                user_preferences=None
            )
    
    
    async def record_recommendation_feedback(
        self, 
        user_id: str, 
        content_id: int, 
        feedback_type: str,
        context: Optional[str] = None
    ):
        """추천 피드백 기록"""
        try:
            # 1. 피드백 기록
            await self.db.execute("""
                INSERT INTO recommendation_feedback 
                (user_id, content_id, feedback_type, context, created_at)
                VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
            """, user_id, content_id, feedback_type, context)
            
            # 2. 사용자 상호작용 업데이트
            if feedback_type in ['like', 'save', 'share']:
                # 콘텐츠의 키워드들과 카테고리에 대한 선호도 업데이트
                await self._update_user_preferences_from_feedback(
                    user_id, content_id, feedback_type
                )
            
            logger.bind(user_id=user_id).info(
                f"Recorded recommendation feedback: {feedback_type} for content {content_id}"
            )
            
        except Exception as e:
            logger.error(f"Failed to record recommendation feedback: {str(e)}")
            raise
    
    # 내부 헬퍼 메서드들
    async def _get_candidate_content_ids(
        self, 
        user_id: str, 
        category_filter: Optional[str], 
        exclude_seen: bool, 
        limit: int
    ) -> List[int]:
        """후보 콘텐츠 ID 조회"""
        conditions = []
        params = []
        param_count = 0
        
        if category_filter:
            param_count += 1
            conditions.append(f"c.name = ${param_count}")
            params.append(category_filter)
        
        if exclude_seen:
            param_count += 1
            conditions.append(f"""
                s.id NOT IN (
                    SELECT content_id FROM user_seen_content WHERE user_id = ${param_count}
                )
            """)
            params.append(user_id)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        param_count += 1
        
        query = f"""
            SELECT s.id
            FROM summaries s
            JOIN categories c ON s.category_id = c.id
            {where_clause}
            ORDER BY s.created_at DESC
            LIMIT ${param_count}
        """
        params.append(limit)
        
        results = await self.db.fetch_all(query, *params)
        return [row['id'] for row in results]
    
    async def _get_content_keywords(self, content_id: int) -> List[str]:
        """콘텐츠의 키워드 조회"""
        keywords = await self.db.fetch_all("""
            SELECT k.keyword
            FROM content_keywords ck
            JOIN keywords k ON ck.keyword_id = k.id
            WHERE ck.content_id = $1
            ORDER BY ck.relevance_score DESC
        """, content_id)
        
        return [kw['keyword'] for kw in keywords]
    
    async def _get_user_frequent_tags(self, user_id: str, limit: int) -> List[Dict]:
        """사용자 자주 사용 태그 조회"""
        return await self.user_profiling.get_user_top_keywords(user_id, limit)
    
    def _merge_and_rank_tags(
        self, 
        user_tags: List[str], 
        ai_tags: List[str], 
        target_count: int
    ) -> List[str]:
        """사용자 태그와 AI 태그 병합 및 순위화"""
        # 사용자 태그 우선, 중복 제거
        merged_tags = []
        seen_tags = set()
        
        # 사용자 태그 먼저 추가
        for tag in user_tags:
            if tag.lower() not in seen_tags and len(merged_tags) < target_count:
                merged_tags.append(tag)
                seen_tags.add(tag.lower())
        
        # AI 태그 추가
        for tag in ai_tags:
            if tag.lower() not in seen_tags and len(merged_tags) < target_count:
                merged_tags.append(tag)
                seen_tags.add(tag.lower())
        
        return merged_tags
    
    async def _build_recommendation_response(
        self, 
        scored_content: List[Tuple[int, float]], 
        algorithm: str,
        user_id: str
    ) -> List[RecommendedContent]:
        """추천 응답 구성"""
        recommendations = []
        
        for content_id, score in scored_content:
            # 콘텐츠 상세 정보 조회
            content_info = await self.db.fetch_one("""
                SELECT s.title, s.summary, s.url, s.created_at, c.name as category
                FROM summaries s
                JOIN categories c ON s.category_id = c.id
                WHERE s.id = $1
            """, content_id)
            
            if content_info:
                keywords = await self._get_content_keywords(content_id)
                
                recommendation = RecommendedContent(
                    content_id=content_id,
                    title=content_info['title'],
                    summary=content_info['summary'],
                    url=content_info['url'],
                    category=content_info['category'],
                    keywords=keywords,
                    similarity_score=score,
                    recommendation_reason=f"{algorithm} 알고리즘 기반",
                    created_at=content_info['created_at']
                )
                recommendations.append(recommendation)
        
        return recommendations
    
    async def _get_user_preference_summary(self, user_id: str) -> Dict:
        """사용자 선호도 요약 정보"""
        top_keywords = await self.user_profiling.get_user_top_keywords(user_id, 5)
        top_categories = await self.user_profiling.get_user_top_categories(user_id, 3)
        diversity_score = await self.user_profiling.calculate_user_diversity_score(user_id)
        
        return {
            "top_keywords": [kw['keyword'] for kw in top_keywords],
            "top_categories": [cat['name'] for cat in top_categories],
            "diversity_score": diversity_score
        }
    
    async def _get_fallback_recommendations(self, limit: int) -> ContentRecommendationResponse:
        """폴백 추천 (인기 콘텐츠)"""
        popular_content = await self.db.fetch_all("""
            SELECT s.id, s.title, s.summary, s.url, s.created_at, c.name as category
            FROM summaries s
            JOIN categories c ON s.category_id = c.id
            ORDER BY s.created_at DESC
            LIMIT $1
        """, limit)
        
        recommendations = []
        for row in popular_content:
            keywords = await self._get_content_keywords(row['id'])
            
            recommendation = RecommendedContent(
                content_id=row['id'],
                title=row['title'],
                summary=row['summary'],
                url=row['url'],
                category=row['category'],
                keywords=keywords,
                similarity_score=0.5,
                recommendation_reason="인기 콘텐츠",
                created_at=row['created_at']
            )
            recommendations.append(recommendation)
        
        return ContentRecommendationResponse(
            recommendations=recommendations,
            total_count=len(recommendations),
            algorithm_used="fallback",
            user_preferences=None
        )
    
    async def _update_user_preferences_from_feedback(
        self, 
        user_id: str, 
        content_id: int, 
        feedback_type: str
    ):
        """피드백 기반 사용자 선호도 업데이트"""
        # 콘텐츠의 키워드들에 대한 선호도 업데이트
        keyword_ids = await self.db.fetch_all("""
            SELECT keyword_id FROM content_keywords WHERE content_id = $1
        """, content_id)
        
        for row in keyword_ids:
            await self.user_profiling.update_user_keyword_interaction(
                user_id, row['keyword_id'], feedback_type
            )
        
        # 콘텐츠의 카테고리에 대한 선호도 업데이트
        category_result = await self.db.fetch_one("""
            SELECT category_id FROM summaries WHERE id = $1
        """, content_id)
        
        if category_result:
            await self.user_profiling.update_user_category_preference(
                user_id, category_result['category_id'], feedback_type
            )

async def get_recommendation_service(db=Depends(get_db)) -> RecommendationService:
    """추천 서비스 의존성"""
    return RecommendationService(db)
