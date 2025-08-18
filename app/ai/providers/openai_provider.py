"""
OpenAI Provider 구현

OpenAI API를 사용하여 AI Provider Interface를 구현합니다.
"""

import openai
from typing import List, Dict, Any, Optional

from .interface import AIProviderInterface, AIResponse
from app.core.config import settings
from app.core.logging import get_logger
from app.metrics import count_tokens

logger = get_logger(__name__)


class OpenAIProvider(AIProviderInterface):
    """OpenAI API Provider"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = openai.AsyncOpenAI(api_key=api_key)
        logger.info(f"{self.provider_name} provider initialized")
    
    def _get_provider_name(self) -> str:
        return "openai"
    
    async def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> AIResponse:
        """채팅 완성 생성"""
        try:
            logger.bind(ai=True).info(f"Generating chat completion with model: {model}")
            
            # 입력 토큰 수 계산
            full_prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
            input_tokens = self.count_tokens(full_prompt, model)
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            content = response.choices[0].message.content
            output_tokens = self.count_tokens(content, model)
            
            logger.bind(ai=True).info(f"Generated chat completion: {len(content)} chars")
            
            return AIResponse(
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_used=model,
                provider=self.provider_name,
                metadata={"temperature": temperature, "max_tokens": max_tokens}
            )
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to generate chat completion: {str(e)}")
            raise Exception(f"OpenAI API 호출 중 오류: {str(e)}")
    
    async def generate_webpage_tags(
        self,
        summary: str,
        similar_tags: List[str] = None,
        tag_count: int = 5,
        model: str = None,
        **kwargs
    ) -> List[str]:
        """웹페이지 태그 생성"""
        if not model:
            model = settings.OPENAI_MODEL
            
        try:
            logger.bind(ai=True).info(f"Generating tags for summary (length: {len(summary)})")
            
            prompt = f"""
            다음 웹페이지 내용을 분석하여 {tag_count}개의 태그를 생성해주세요.
            바로 저장할 수 있도록 응답은 태그만 작성해주세요.
            각 태그는 쉼표로 구분해주세요.
            태그는 한글 또는 영어의 명사형 단어로 작성해주세요.
            사용자가 이전에 저장한 유사 태그가 있다면, 그 태그도 함께 고려해주세요.
            {', '.join(similar_tags) if similar_tags else '없음'}
            
            summary: {summary}
            """
            
            system_msg = "당신은 웹페이지 내용을 분석하는 전문가입니다."
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=kwargs.get('max_tokens', 100),
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            tags = [k.strip() for k in content.split(',') if k.strip()]
            
            logger.bind(ai=True).info(f"Generated {len(tags)} tags: {tags}")
            return tags
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to generate tags: {str(e)}")
            raise Exception(f"OpenAI API 호출 중 오류: {str(e)}")
    
    async def recommend_webpage_category(
        self,
        summary: str,
        similar_categories: List[str] = None,
        model: str = None,
        **kwargs
    ) -> str:
        """웹페이지 카테고리 추천"""
        if not model:
            model = settings.OPENAI_MODEL
            
        try:
            logger.bind(ai=True).info(f"Recommending category for summary (length: {len(summary)})")
            
            prompt = f"""
            다음 웹페이지 내용을 분석하여 적절한 단 하나의 카테고리를 추천해주세요.
            바로 저장할 수 있도록 카테고리만 작성해주세요.
            사용자가 이전에 저장한 유사 카테고리가 있다면, 그 카테고리도 함께 고려해주세요.
            {', '.join(similar_categories) if similar_categories else '없음'}
            카테고리는 반드시 하나여야 하며, 여러 개의 카테고리를 추천하지 마세요.
            사용자가 이전에 저장한 카테고리중 적합한게 없다면 새로 추천해주세요.

            summary: {summary}
            """
            
            system_msg = "당신은 웹페이지 내용을 분석하는 전문가입니다."
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=kwargs.get('max_tokens', 100),
                temperature=0.3
            )
            
            content = response.choices[0].message.content.strip()
            
            logger.bind(ai=True).info(f"Recommended category: {content}")
            return content
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to recommend category: {str(e)}")
            raise Exception(f"OpenAI API 호출 중 오류: {str(e)}")
    
    async def generate_webpage_summary(
        self,
        url: str,
        html_content: str,
        model: str = None,
        max_tokens: int = 500,
        **kwargs
    ) -> str:
        """웹페이지 요약 생성"""
        if not model:
            model = settings.OPENAI_MODEL
            
        try:
            logger.bind(ai=True).info("Generating summary for URL = %s", url)

            prompt = f"""
            다음 웹페이지 내용을 분석하여 요약을 생성해주세요.
            바로 저장할 수 있도록 요약만 작성해주세요.
            
            URL: {url}
            """
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "당신은 웹페이지 내용을 분석하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )

            content = response.choices[0].message.content.strip()
            logger.bind(ai=True).info(f"Generated summary (length: {len(content)})")
            return content
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to generate summary for {url}: {str(e)}")
            raise Exception(f"OpenAI API 호출 중 오류: {str(e)}")
    
    async def generate_youtube_summary(
        self,
        title: str,
        transcript: str,
        model: str = None,
        **kwargs
    ) -> str:
        """YouTube 동영상 요약 생성"""
        if not model:
            model = settings.OPENAI_MODEL
            
        try:
            logger.bind(ai=True).info(f"Generating YouTube summary for video: {title[:50]}...")
            
            prompt = f"""
            다음 YouTube 동영상의 제목과 스크립트를 분석하여 핵심 내용을 요약해주세요.
            요약은 동영상의 주요 내용, 핵심 메시지, 중요한 정보를 포함해야 합니다.
            요약은 한국어로 작성하고, 3-5문장으로 간결하게 작성해주세요.

            제목: {title}
            
            스크립트:
            {transcript[:3000]}
            """
            
            system_msg = "당신은 YouTube 동영상 콘텐츠를 분석하는 전문가입니다."
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            summary = response.choices[0].message.content.strip()
            
            logger.bind(ai=True).info(f"YouTube summary generated successfully (length: {len(summary)})")
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate YouTube summary: {str(e)}")
            raise Exception(f"OpenAI API 호출 중 오류: {str(e)}")
    
    async def generate_youtube_tags(
        self,
        title: str,
        summary: str,
        tag_count: int = 5,
        model: str = None,
        **kwargs
    ) -> List[str]:
        """YouTube 동영상 태그 생성"""
        if not model:
            model = settings.OPENAI_MODEL
            
        try:
            logger.bind(ai=True).info(f"Generating YouTube tags for video: {title[:50]}...")
            
            prompt = f"""
            다음 YouTube 동영상의 제목과 요약을 분석하여 {tag_count}개의 태그를 생성해주세요.
            태그는 동영상의 주제, 카테고리, 핵심 키워드를 반영해야 합니다.
            각 태그는 쉼표로 구분해주세요.
            태그는 한글 또는 영어의 명사형 단어로 작성해주세요.

            제목: {title}
            요약: {summary}
            """
            
            system_msg = "당신은 YouTube 콘텐츠를 분석하는 태그 생성 전문가입니다."
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=100
            )
            
            tags_text = response.choices[0].message.content.strip()
            tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
            
            logger.bind(ai=True).info(f"YouTube tags generated: {tags}")
            return tags
            
        except Exception as e:
            logger.error(f"Failed to generate YouTube tags: {str(e)}")
            raise Exception(f"OpenAI API 호출 중 오류: {str(e)}")
    
    async def recommend_youtube_category(
        self,
        title: str,
        summary: str,
        model: str = None,
        **kwargs
    ) -> str:
        """YouTube 동영상 카테고리 추천"""
        if not model:
            model = settings.OPENAI_MODEL
            
        try:
            logger.bind(ai=True).info(f"Recommending YouTube category for video: {title[:50]}...")
            
            prompt = f"""
            다음 YouTube 동영상의 제목과 요약을 분석하여 가장 적합한 카테고리를 추천해주세요.
            카테고리는 다음 중 하나여야 합니다:
            Education, Entertainment, Technology, Music, Gaming, Sports, News, Lifestyle, Tutorial, Review, Vlog, Comedy, Science, Business, Art

            제목: {title}
            요약: {summary}

            카테고리명만 응답해주세요.
            """
            
            system_msg = "당신은 YouTube 콘텐츠를 분석하는 카테고리 분류 전문가입니다."
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=50
            )
            
            category = response.choices[0].message.content.strip()
            
            logger.bind(ai=True).info(f"YouTube category recommended: {category}")
            return category
            
        except Exception as e:
            logger.error(f"Failed to recommend YouTube category: {str(e)}")
            raise Exception(f"OpenAI API 호출 중 오류: {str(e)}")
    
    def count_tokens(self, text: str, model: str) -> int:
        """텍스트의 토큰 수 계산"""
        return count_tokens(text, model)
    
    def _extract_text_from_html(self, html_content: str) -> str:
        """HTML에서 텍스트 추출"""
        import re
        text = re.sub(r'<[^>]+>', '', html_content)
        text = re.sub(r'\s+', ' ', text).strip()
        return text