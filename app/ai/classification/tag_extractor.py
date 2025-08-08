from typing import List
import openai
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("tag_extraction")


class TagExtractionService:
    """태그 추출 서비스 (기존 openai_service.py에서 이전)"""
    
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        logger.info("Tag extraction service initialized")
    
    async def extract_tags_from_summary(
        self, 
        summary: str,
        similar_tags: List[str] = None,
        tag_count: int = 5,
        max_tokens: int = 100
    ) -> List[str]:
        """요약문에서 태그 추출 (기존 generate_webpage_tags 메서드)"""
        try:
            logger.bind(ai=True).info(f"Extracting tags from summary (length: {len(summary)})")
            
            prompt = f"""
            다음 웹페이지 내용을 분석하여 {tag_count}개의 태그를 생성해주세요.
            바로 저장할 수 있도록 응답은 태그만 작성해주세요.
            각 태그는 쉼표로 구분해주세요.
            태그는 한글 또는 영어의 명사형 단어로 작성해주세요.
            사용자가 이전에 저장한 유사 태그가 있다면, 그 태그도 함께 고려해주세요.
            유사 태그: {', '.join(similar_tags) if similar_tags else '없음'}
            
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
            
            content = response.choices[0].message.content
            tags = [tag.strip() for tag in content.split(',') if tag.strip()]
            
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