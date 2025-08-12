from typing import List
import openai
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class CategoryClassificationService:
    """카테고리 분류 서비스 (기존 openai_service.py에서 이전)"""
    
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        logger.info("Category classification service initialized")
    
    async def classify_category_from_summary(
        self,
        summary: str,
        similar_categories: List[str] = None,
        max_tokens: int = 50
    ) -> str:
        """요약문에서 카테고리 분류 (기존 recommend_webpage_category 메서드)"""
        try:
            logger.bind(ai=True).info(f"Classifying category from summary (length: {len(summary)})")
            
            prompt = f"""
            다음 웹페이지 내용을 분석하여 적절한 단 하나의 카테고리를 추천해주세요.
            바로 저장할 수 있도록 카테고리만 작성해주세요.
            사용자가 이전에 저장한 유사 카테고리가 있다면, 그 카테고리도 함께 고려해주세요.
            유사 카테고리: {', '.join(similar_categories) if similar_categories else '없음'}
            카테고리는 반드시 하나여야 하며, 여러 개의 카테고리를 추천하지 마세요.
            사용자가 이전에 저장한 카테고리중 적합한게 없다면 새로 추천해주세요.

            요약: {summary}
            """
            
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    ChatCompletionSystemMessageParam(content="당신은 웹페이지 내용을 분석하는 전문가입니다.", role="system"),
                    ChatCompletionUserMessageParam(content=prompt, role="user")
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )
            
            category = response.choices[0].message.content.strip()
            
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