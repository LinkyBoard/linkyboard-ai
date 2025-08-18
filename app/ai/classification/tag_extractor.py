from typing import List
from app.ai.providers.router import ai_router
from app.core.logging import get_logger

logger = get_logger(__name__)


class TagExtractionService:
    """태그 추출 서비스 (AI Router 기반)"""
    
    def __init__(self):
        logger.info("Tag extraction service initialized")
    
    async def extract_tags_from_summary(
        self, 
        summary: str,
        similar_tags: List[str] = None,
        tag_count: int = 5,
        max_tokens: int = 100,
        user_id: int = None
    ) -> List[str]:
        """요약문에서 태그 추출 (AI Router 기반)"""
        try:
            logger.bind(ai=True).info(f"Extracting tags from summary (length: {len(summary)})")
            
            # AI Router를 통해 태그 생성
            tags = await ai_router.generate_webpage_tags(
                summary=summary,
                similar_tags=similar_tags,
                tag_count=tag_count,
                user_id=user_id,
                max_tokens=max_tokens
            )
            
            logger.bind(ai=True).info(f"Extracted {len(tags)} tags: {tags}")
            return tags
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to extract tags: {str(e)}")
            raise Exception(f"태그 추출 실패: {str(e)}")
    
    async def extract_tags_from_content(
        self,
        content: str,
        user_history_tags: List[str] = None,
        tag_count: int = 5
    ) -> List[str]:
        """원본 콘텐츠에서 직접 태그 추출"""
        try:
            # 콘텐츠가 너무 길면 요약부터 생성
            if len(content) > 2000:
                # 여기서 요약 서비스를 호출할 수 있음
                # 일단은 앞부분만 사용
                content = content[:2000] + "..."
            
            return await self.extract_tags_from_summary(
                summary=content,
                similar_tags=user_history_tags,
                tag_count=tag_count
            )
            
        except Exception as e:
            logger.error(f"Failed to extract tags from content: {str(e)}")
            raise