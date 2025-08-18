from typing import List
from app.ai.providers.router import ai_router
from app.core.logging import get_logger

logger = get_logger(__name__)


class CategoryClassificationService:
    """카테고리 분류 서비스 (AI Router 기반)"""
    
    def __init__(self):
        logger.info("Category classification service initialized")
    
    async def classify_category_from_summary(
        self,
        summary: str,
        similar_categories: List[str] = None,
        max_tokens: int = 50,
        user_id: int = None
    ) -> str:
        """요약문에서 카테고리 분류 (AI Router 기반)"""
        try:
            logger.bind(ai=True).info(f"Classifying category from summary (length: {len(summary)})")
            
            # AI Router를 통해 카테고리 추천
            category = await ai_router.recommend_webpage_category(
                summary=summary,
                similar_categories=similar_categories,
                user_id=user_id,
                max_tokens=max_tokens
            )
            
            logger.bind(ai=True).info(f"Classified category: '{category}'")
            return category
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to classify category: {str(e)}")
            raise Exception(f"카테고리 분류 실패: {str(e)}")
    
    async def classify_category_from_content(
        self,
        content: str,
        user_history_categories: List[str] = None
    ) -> str:
        """원본 콘텐츠에서 직접 카테고리 분류"""
        try:
            # 콘텐츠가 너무 길면 요약부터 생성
            if len(content) > 2000:
                content = content[:2000] + "..."
            
            return await self.classify_category_from_summary(
                summary=content,
                similar_categories=user_history_categories
            )
            
        except Exception as e:
            logger.error(f"Failed to classify category from content: {str(e)}")
            raise