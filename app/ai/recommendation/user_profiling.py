import numpy as np
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from app.core.logging import get_logger

logger = get_logger(__name__)


class UserProfilingService:
    """사용자 프로파일링 서비스 - 사용자 선호도 분석 및 벡터 생성"""
    
    def __init__(self, db_connection):
        self.db = db_connection
        logger.info("User profiling service initialized")
    
    async def update_user_keyword_interaction(
        self, 
        user_id: str, 
        keyword_id: int, 
        interaction_type: str = "view"
    ):
        """사용자-키워드 상호작용 업데이트"""
        try:
            # 상호작용 타입별 점수
            interaction_scores = {
                "view": 1.0,
                "save": 2.0,
                "share": 1.5,
                "like": 2.5
            }
            
            score_increment = interaction_scores.get(interaction_type, 1.0)
            
            await self.db.execute("""
                INSERT INTO user_keyword_interactions 
                (user_id, keyword_id, interaction_count, preference_score, last_interaction)
                VALUES ($1, $2, 1, $3, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, keyword_id)
                DO UPDATE SET 
                    interaction_count = user_keyword_interactions.interaction_count + 1,
                    preference_score = user_keyword_interactions.preference_score + $3,
                    last_interaction = CURRENT_TIMESTAMP
            """, user_id, keyword_id, score_increment)
            
            logger.bind(user_id=user_id).info(
                f"Updated keyword interaction: keyword_id={keyword_id}, type={interaction_type}"
            )
            
        except Exception as e:
            logger.error(f"Failed to update user keyword interaction: {str(e)}")
            raise
    
    async def update_user_category_preference(
        self, 
        user_id: str, 
        category_id: int, 
        interaction_type: str = "view"
    ):
        """사용자-카테고리 선호도 업데이트"""
        try:
            interaction_scores = {
                "view": 1.0,
                "save": 3.0,
                "share": 2.0,
                "like": 3.5
            }
            
            score_increment = interaction_scores.get(interaction_type, 1.0)
            
            await self.db.execute("""
                INSERT INTO user_category_preferences 
                (user_id, category_id, frequency_count, preference_score, last_used)
                VALUES ($1, $2, 1, $3, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, category_id)
                DO UPDATE SET 
                    frequency_count = user_category_preferences.frequency_count + 1,
                    preference_score = user_category_preferences.preference_score + $3,
                    last_used = CURRENT_TIMESTAMP
            """, user_id, category_id, score_increment)
            
            logger.bind(user_id=user_id).info(
                f"Updated category preference: category_id={category_id}, type={interaction_type}"
            )
            
        except Exception as e:
            logger.error(f"Failed to update user category preference: {str(e)}")
            raise
    
    async def get_user_preference_vector(self, user_id: str) -> Optional[List[float]]:
        """사용자 선호도 벡터 생성"""
        try:
            # 최근 활동에 더 높은 가중치를 주기 위한 시간 가중치 계산
            current_time = datetime.utcnow()
            decay_days = 30  # 30일 후 가중치 절반
            
            # 사용자가 상호작용한 키워드들과 선호도 조회
            user_keywords = await self.db.fetch_all("""
                SELECT 
                    k.embedding, 
                    uk.preference_score, 
                    uk.interaction_count,
                    uk.last_interaction,
                    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - uk.last_interaction)) / (24 * 3600) as days_ago
                FROM user_keyword_interactions uk
                JOIN keywords k ON uk.keyword_id = k.id
                WHERE uk.user_id = $1 AND uk.interaction_count > 0
            """, user_id)
            
            if not user_keywords:
                logger.info(f"No keyword interactions found for user {user_id}")
                return None
            
            vectors = []
            weights = []
            
            for row in user_keywords:
                embedding = np.array(row['embedding'])
                
                # 시간 가중치 (최근일수록 높은 가중치)
                time_weight = np.exp(-row['days_ago'] / decay_days)
                
                # 최종 가중치 = 선호도 점수 * 상호작용 로그 * 시간 가중치
                final_weight = (
                    row['preference_score'] * 
                    np.log(1 + row['interaction_count']) * 
                    time_weight
                )
                
                vectors.append(embedding * final_weight)
                weights.append(final_weight)
            
            # 가중 평균으로 사용자 벡터 계산
            user_vector = np.average(vectors, axis=0, weights=weights)
            
            logger.bind(user_id=user_id).info(
                f"Generated user preference vector from {len(user_keywords)} keyword interactions"
            )
            
            return user_vector.tolist()
            
        except Exception as e:
            logger.error(f"Failed to generate user preference vector for {user_id}: {str(e)}")
            return None
    
    async def get_user_top_keywords(self, user_id: str, limit: int = 20) -> List[Dict]:
        """사용자 상위 선호 키워드 조회"""
        try:
            top_keywords = await self.db.fetch_all("""
                SELECT 
                    k.keyword,
                    uk.preference_score,
                    uk.interaction_count,
                    uk.last_interaction
                FROM user_keyword_interactions uk
                JOIN keywords k ON uk.keyword_id = k.id
                WHERE uk.user_id = $1
                ORDER BY uk.preference_score DESC, uk.interaction_count DESC
                LIMIT $2
            """, user_id, limit)
            
            return [dict(row) for row in top_keywords]
            
        except Exception as e:
            logger.error(f"Failed to get user top keywords for {user_id}: {str(e)}")
            return []
    
    async def get_user_top_categories(self, user_id: str, limit: int = 10) -> List[Dict]:
        """사용자 상위 선호 카테고리 조회"""
        try:
            top_categories = await self.db.fetch_all("""
                SELECT 
                    c.name,
                    ucp.preference_score,
                    ucp.frequency_count,
                    ucp.last_used
                FROM user_category_preferences ucp
                JOIN categories c ON ucp.category_id = c.id
                WHERE ucp.user_id = $1
                ORDER BY ucp.preference_score DESC, ucp.frequency_count DESC
                LIMIT $2
            """, user_id, limit)
            
            return [dict(row) for row in top_categories]
            
        except Exception as e:
            logger.error(f"Failed to get user top categories for {user_id}: {str(e)}")
            return []
    
    async def calculate_user_diversity_score(self, user_id: str) -> float:
        """사용자 관심사 다양성 점수 계산"""
        try:
            # 사용자가 상호작용한 카테고리 수와 분포도 계산
            category_distribution = await self.db.fetch_all("""
                SELECT 
                    c.name,
                    ucp.preference_score,
                    ucp.frequency_count
                FROM user_category_preferences ucp
                JOIN categories c ON ucp.category_id = c.id
                WHERE ucp.user_id = $1
                ORDER BY ucp.preference_score DESC
            """, user_id)
            
            if len(category_distribution) <= 1:
                return 0.0  # 다양성 없음
            
            # 엔트로피 기반 다양성 계산
            total_interactions = sum(row['frequency_count'] for row in category_distribution)
            if total_interactions == 0:
                return 0.0
            
            entropy = 0.0
            for row in category_distribution:
                p = row['frequency_count'] / total_interactions
                if p > 0:
                    entropy -= p * np.log2(p)
            
            # 정규화 (0~1 사이)
            max_entropy = np.log2(len(category_distribution))
            diversity_score = entropy / max_entropy if max_entropy > 0 else 0.0
            
            logger.bind(user_id=user_id).info(f"User diversity score: {diversity_score:.3f}")
            return diversity_score
            
        except Exception as e:
            logger.error(f"Failed to calculate user diversity score for {user_id}: {str(e)}")
            return 0.0