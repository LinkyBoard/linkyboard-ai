import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from app.core.logging import get_logger

logger = get_logger(__name__)


class ContentScoringService:
    """콘텐츠 스코어링 서비스 - 추천 점수 계산"""
    
    def __init__(self, db_connection):
        self.db = db_connection
        logger.info("Content scoring service initialized")
    
    async def calculate_content_score_for_user(
        self, 
        user_id: str, 
        content_id: int,
        user_vector: Optional[List[float]] = None
    ) -> float:
        """특정 사용자에 대한 콘텐츠 점수 계산"""
        try:
            # 기본 점수들
            scores = {
                'vector_similarity': 0.0,
                'category_preference': 0.0,
                'keyword_overlap': 0.0,
                'freshness': 0.0,
                'popularity': 0.0
            }
            
            # 1. 벡터 유사도 점수 (40%)
            if user_vector:
                vector_score = await self._calculate_vector_similarity_score(
                    user_vector, content_id
                )
                scores['vector_similarity'] = vector_score * 0.4
            
            # 2. 카테고리 선호도 점수 (25%)
            category_score = await self._calculate_category_preference_score(
                user_id, content_id
            )
            scores['category_preference'] = category_score * 0.25
            
            # 3. 키워드 겹침 점수 (20%)
            keyword_score = await self._calculate_keyword_overlap_score(
                user_id, content_id
            )
            scores['keyword_overlap'] = keyword_score * 0.20
            
            # 4. 신선도 점수 (10%)
            freshness_score = await self._calculate_freshness_score(content_id)
            scores['freshness'] = freshness_score * 0.10
            
            # 5. 인기도 점수 (5%)
            popularity_score = await self._calculate_popularity_score(content_id)
            scores['popularity'] = popularity_score * 0.05
            
            total_score = sum(scores.values())
            
            logger.bind(user_id=user_id, content_id=content_id).debug(
                f"Content scores: {scores}, total: {total_score:.3f}"
            )
            
            return total_score
            
        except Exception as e:
            logger.error(f"Failed to calculate content score for user {user_id}, content {content_id}: {str(e)}")
            return 0.0
    
    async def _calculate_vector_similarity_score(
        self, 
        user_vector: List[float], 
        content_id: int
    ) -> float:
        """벡터 유사도 점수 계산"""
        try:
            content_embedding = await self.db.fetch_one("""
                SELECT embedding FROM content_embeddings WHERE content_id = $1
            """, content_id)
            
            if not content_embedding or not content_embedding['embedding']:
                return 0.0
            
            # 코사인 유사도 계산
            user_vec = np.array(user_vector)
            content_vec = np.array(content_embedding['embedding'])
            
            dot_product = np.dot(user_vec, content_vec)
            norm_user = np.linalg.norm(user_vec)
            norm_content = np.linalg.norm(content_vec)
            
            if norm_user == 0 or norm_content == 0:
                return 0.0
            
            similarity = dot_product / (norm_user * norm_content)
            return max(0.0, similarity)  # 음수 유사도 제거
            
        except Exception as e:
            logger.error(f"Failed to calculate vector similarity score: {str(e)}")
            return 0.0
    
    async def _calculate_category_preference_score(
        self, 
        user_id: str, 
        content_id: int
    ) -> float:
        """카테고리 선호도 점수 계산"""
        try:
            result = await self.db.fetch_one("""
                SELECT ucp.preference_score, ucp.frequency_count
                FROM summaries s
                JOIN user_category_preferences ucp ON s.category_id = ucp.category_id
                WHERE s.id = $1 AND ucp.user_id = $2
            """, content_id, user_id)
            
            if not result:
                return 0.0
            
            # 선호도 점수와 빈도를 고려한 정규화
            preference_score = result['preference_score']
            frequency = result['frequency_count']
            
            # 로그 스케일로 정규화
            normalized_score = np.log(1 + preference_score) / 10.0
            frequency_boost = np.log(1 + frequency) / 5.0
            
            return min(1.0, normalized_score + frequency_boost * 0.1)
            
        except Exception as e:
            logger.error(f"Failed to calculate category preference score: {str(e)}")
            return 0.0
    
    async def _calculate_keyword_overlap_score(
        self, 
        user_id: str, 
        content_id: int
    ) -> float:
        """키워드 겹침 점수 계산"""
        try:
            # 콘텐츠의 키워드들과 사용자의 선호 키워드들 간 겹침 계산
            overlap_data = await self.db.fetch_all("""
                SELECT 
                    uk.preference_score,
                    uk.interaction_count,
                    ck.relevance_score
                FROM content_keywords ck
                JOIN user_keyword_interactions uk ON ck.keyword_id = uk.keyword_id
                WHERE ck.content_id = $1 AND uk.user_id = $2
            """, content_id, user_id)
            
            if not overlap_data:
                return 0.0
            
            # 가중치 적용된 겹침 점수 계산
            total_score = 0.0
            for row in overlap_data:
                user_weight = np.log(1 + row['preference_score']) * np.log(1 + row['interaction_count'])
                content_weight = row['relevance_score']
                total_score += user_weight * content_weight
            
            # 정규화
            normalized_score = min(1.0, total_score / 10.0)
            return normalized_score
            
        except Exception as e:
            logger.error(f"Failed to calculate keyword overlap score: {str(e)}")
            return 0.0
    
    async def _calculate_freshness_score(self, content_id: int) -> float:
        """신선도 점수 계산"""
        try:
            content_data = await self.db.fetch_one("""
                SELECT created_at FROM summaries WHERE id = $1
            """, content_id)
            
            if not content_data:
                return 0.0
            
            # 콘텐츠 생성 시간 기준 신선도 계산
            created_at = content_data['created_at']
            now = datetime.utcnow()
            
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=now.tzinfo)
            
            hours_ago = (now - created_at).total_seconds() / 3600
            
            # 24시간 내 = 1.0, 일주일 후 = 0.1로 지수적 감소
            freshness = np.exp(-hours_ago / 48)  # 48시간 half-life
            return min(1.0, freshness)
            
        except Exception as e:
            logger.error(f"Failed to calculate freshness score: {str(e)}")
            return 0.0
    
    async def _calculate_popularity_score(self, content_id: int) -> float:
        """인기도 점수 계산"""
        try:
            # 현재 단순 구현 - 향후 조회수, 공유수 등 추가 가능
            # 일단 콘텐츠 ID 기반으로 임시 점수
            popularity = 0.5  # 기본값
            
            # TODO: 실제 인기도 메트릭 구현
            # - 조회수
            # - 공유수
            # - 좋아요수
            
            return popularity
            
        except Exception as e:
            logger.error(f"Failed to calculate popularity score: {str(e)}")
            return 0.0
    
    async def score_content_batch_for_user(
        self, 
        user_id: str, 
        content_ids: List[int],
        user_vector: Optional[List[float]] = None
    ) -> List[Tuple[int, float]]:
        """사용자에 대한 콘텐츠 배치 점수 계산"""
        try:
            scored_content = []
            
            for content_id in content_ids:
                score = await self.calculate_content_score_for_user(
                    user_id, content_id, user_vector
                )
                scored_content.append((content_id, score))
            
            # 점수 기준 내림차순 정렬
            scored_content.sort(key=lambda x: x[1], reverse=True)
            
            logger.bind(user_id=user_id).info(
                f"Scored {len(content_ids)} contents for user"
            )
            
            return scored_content
            
        except Exception as e:
            logger.error(f"Failed to score content batch for user {user_id}: {str(e)}")
            return [(content_id, 0.0) for content_id in content_ids]