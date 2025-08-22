"""
Google Provider 구현

Google Gemini API를 사용하여 AI Provider Interface를 구현합니다.
"""

from typing import List, Dict, Any, Optional
import tiktoken

from .interface import AIProviderInterface, AIResponse
from app.core.logging import get_logger

logger = get_logger(__name__)


class GoogleProvider(AIProviderInterface):
    """Google Gemini API Provider"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self._genai = genai
            self._google_available = True
            logger.info(f"{self.provider_name} provider initialized")
        except ImportError:
            logger.warning("google-generativeai package not installed, Google provider disabled")
            self._google_available = False
            self._genai = None
    
    def _get_provider_name(self) -> str:
        return "google"
    
    def is_available(self) -> bool:
        """Google provider 사용 가능 여부 확인"""
        return self._google_available and bool(self.api_key)
    
    def _format_messages_for_gemini(self, messages: List[Dict[str, str]]) -> str:
        """메시지를 Gemini 형식으로 변환"""
        formatted_prompt = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "system":
                formatted_prompt += f"Instructions: {content}\n\n"
            elif role == "user":
                formatted_prompt += f"User: {content}\n\n"
            elif role == "assistant":
                formatted_prompt += f"Assistant: {content}\n\n"
        
        return formatted_prompt.strip()
    
    async def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> AIResponse:
        """채팅 완성 생성"""
        if not self.is_available():
            raise Exception("Google provider is not available. Please install 'google-generativeai' package.")
        
        try:
            logger.bind(ai=True).info(f"Generating chat completion with Google model: {model}")
            
            # Gemini 모델 생성
            gemini_model = self._genai.GenerativeModel(model)
            
            # 메시지 형식 변환
            prompt = self._format_messages_for_gemini(messages)
            
            # 입력 토큰 수 계산
            input_tokens = self.count_tokens(prompt, model)
            
            # 생성 설정
            generation_config = self._genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature
            )
            
            response = await gemini_model.generate_content_async(
                prompt,
                generation_config=generation_config
            )
            
            content = response.text
            output_tokens = self.count_tokens(content, model)
            
            logger.bind(ai=True).info(f"Generated Google chat completion: {len(content)} chars")
            
            return AIResponse(
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_used=model,
                provider=self.provider_name,
                metadata={"temperature": temperature, "max_tokens": max_tokens}
            )
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to generate Google chat completion: {str(e)}")
            raise Exception(f"Google API 호출 중 오류: {str(e)}")
    
    async def generate_webpage_tags(
        self,
        summary: str,
        similar_tags: List[str] = None,
        tag_count: int = 5,
        model: str = "gemini-pro",
        **kwargs
    ) -> List[str]:
        """웹페이지 태그 생성"""
        if not self.is_available():
            raise Exception("Google provider is not available.")
            
        try:
            logger.bind(ai=True).info(f"Generating tags with Google for summary (length: {len(summary)})")
            
            prompt = f"""다음 웹페이지 내용을 분석하여 {tag_count}개의 태그를 생성해주세요.
바로 저장할 수 있도록 응답은 태그만 작성해주세요.
각 태그는 쉼표로 구분해주세요.
태그는 한글 또는 영어의 명사형 단어로 작성해주세요.
사용자가 이전에 저장한 유사 태그가 있다면, 그 태그도 함께 고려해주세요.
{', '.join(similar_tags) if similar_tags else '없음'}

summary: {summary}"""
            
            gemini_model = self._genai.GenerativeModel(model)
            generation_config = self._genai.types.GenerationConfig(
                max_output_tokens=kwargs.get('max_tokens', 100),
                temperature=0.3
            )
            
            response = await gemini_model.generate_content_async(
                prompt,
                generation_config=generation_config
            )
            
            content = response.text
            tags = [k.strip() for k in content.split(',') if k.strip()]
            
            logger.bind(ai=True).info(f"Generated {len(tags)} tags with Google: {tags}")
            return tags
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to generate tags with Google: {str(e)}")
            raise Exception(f"Google API 호출 중 오류: {str(e)}")
    
    async def recommend_webpage_category(
        self,
        summary: str,
        similar_categories: List[str] = None,
        model: str = "gemini-pro",
        **kwargs
    ) -> str:
        """웹페이지 카테고리 추천"""
        if not self.is_available():
            raise Exception("Google provider is not available.")
            
        try:
            logger.bind(ai=True).info(f"Recommending category with Google for summary (length: {len(summary)})")
            
            prompt = f"""다음 웹페이지 내용을 분석하여 적절한 단 하나의 카테고리를 추천해주세요.
바로 저장할 수 있도록 카테고리만 작성해주세요.
사용자가 이전에 저장한 유사 카테고리가 있다면, 그 카테고리도 함께 고려해주세요.
{', '.join(similar_categories) if similar_categories else '없음'}
카테고리는 반드시 하나여야 하며, 여러 개의 카테고리를 추천하지 마세요.
사용자가 이전에 저장한 카테고리중 적합한게 없다면 새로 추천해주세요.

summary: {summary}"""
            
            gemini_model = self._genai.GenerativeModel(model)
            generation_config = self._genai.types.GenerationConfig(
                max_output_tokens=kwargs.get('max_tokens', 100),
                temperature=0.3
            )
            
            response = await gemini_model.generate_content_async(
                prompt,
                generation_config=generation_config
            )
            
            content = response.text.strip()
            
            logger.bind(ai=True).info(f"Recommended category with Google: {content}")
            return content
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to recommend category with Google: {str(e)}")
            raise Exception(f"Google API 호출 중 오류: {str(e)}")
    
    async def generate_webpage_summary(
        self,
        url: str,
        html_content: str,
        model: str = "gemini-pro",
        max_tokens: int = 500,
        **kwargs
    ) -> str:
        """웹페이지 요약 생성"""
        from app.core.utils import extract_text_from_html, truncate_text_for_ai
        
        if not self.is_available():
            raise Exception("Google provider is not available.")
            
        try:
            logger.bind(ai=True).info(f"Generating summary with Google for URL: {url}")

            # HTML 내용을 텍스트로 추출
            text_content = extract_text_from_html(html_content)
            
            # AI 토큰 제한에 맞게 텍스트 자르기
            text_content = truncate_text_for_ai(text_content, max_tokens=2500)
            
            # HTML 내용이 있으면 실제 내용으로, 없으면 URL만으로 요약
            if text_content.strip():
                prompt = f"""다음 웹페이지 내용을 분석하여 요약을 생성해주세요.
바로 저장할 수 있도록 요약만 작성해주세요.

URL: {url}

웹페이지 내용:
{text_content}"""
            else:
                prompt = f"""다음 웹페이지 내용을 분석하여 요약을 생성해주세요.
바로 저장할 수 있도록 요약만 작성해주세요.

URL: {url}

참고: 웹페이지의 실제 내용을 추출할 수 없어 URL 기반으로만 요약합니다."""
            
            gemini_model = self._genai.GenerativeModel(model)
            generation_config = self._genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.3
            )
            
            response = await gemini_model.generate_content_async(
                prompt,
                generation_config=generation_config
            )

            content = response.text.strip()
            logger.bind(ai=True).info(f"Generated summary with Google (length: {len(content)})")
            return content
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to generate summary with Google for {url}: {str(e)}")
            raise Exception(f"Google API 호출 중 오류: {str(e)}")
    
    async def generate_youtube_summary(
        self,
        title: str,
        transcript: str,
        model: str = "gemini-pro",
        **kwargs
    ) -> str:
        """YouTube 동영상 요약 생성"""
        if not self.is_available():
            raise Exception("Google provider is not available.")
            
        try:
            logger.bind(ai=True).info(f"Generating YouTube summary with Google for video: {title[:50]}...")
            
            prompt = f"""다양한 언어의 YouTube 비디오 자막을 한국어로 요약하는 작업입니다.

작업 지침:
아래 내용을 완전히 이해하고, 어떤 언어이든 상관없이 자연스러운 한국어로 요약해주세요.

동영상 제목: {title}

자막 콘텐츠:
{transcript[:3000]}

요약 요구사항:
• 자막이 영어, 일본어, 중국어, 프랑스어, 독일어, 스페인어 등 어떤 언어이든 상관없이 내용을 완전히 파악하여 한국어로 재작성
• 3-5문장의 자연스럽고 이해하기 쉬운 한국어 요약
• 동영상의 핵심 내용, 주요 메시지, 중요 정보를 모두 포함
• 전문적이고 가독성 높은 한국어 표현 사용

❌ 금지사항: 영어, 일본어 등 한국어 이외의 언어 사용 절대 금지. 반드시 한국어로만 작성."""
            
            gemini_model = self._genai.GenerativeModel(model)
            generation_config = self._genai.types.GenerationConfig(
                max_output_tokens=500,
                temperature=0.7
            )
            
            response = await gemini_model.generate_content_async(
                prompt,
                generation_config=generation_config
            )
            
            summary = response.text.strip()
            
            logger.bind(ai=True).info(f"YouTube summary generated with Google (length: {len(summary)})")
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate YouTube summary with Google: {str(e)}")
            raise Exception(f"Google API 호출 중 오류: {str(e)}")
    
    async def generate_youtube_tags(
        self,
        title: str,
        summary: str,
        tag_count: int = 5,
        model: str = "gemini-pro",
        **kwargs
    ) -> List[str]:
        """YouTube 동영상 태그 생성"""
        if not self.is_available():
            raise Exception("Google provider is not available.")
            
        try:
            logger.bind(ai=True).info(f"Generating YouTube tags with Google for video: {title[:50]}...")
            
            prompt = f"""다음 YouTube 동영상의 제목과 요약을 분석하여 {tag_count}개의 태그를 생성해주세요.
태그는 동영상의 주제, 카테고리, 핵심 키워드를 반영해야 합니다.
각 태그는 쉼표로 구분해주세요.
태그는 한글 또는 영어의 명사형 단어로 작성해주세요.

제목: {title}
요약: {summary}"""
            
            gemini_model = self._genai.GenerativeModel(model)
            generation_config = self._genai.types.GenerationConfig(
                max_output_tokens=100,
                temperature=0.5
            )
            
            response = await gemini_model.generate_content_async(
                prompt,
                generation_config=generation_config
            )
            
            tags_text = response.text.strip()
            tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
            
            logger.bind(ai=True).info(f"YouTube tags generated with Google: {tags}")
            return tags
            
        except Exception as e:
            logger.error(f"Failed to generate YouTube tags with Google: {str(e)}")
            raise Exception(f"Google API 호출 중 오류: {str(e)}")
    
    async def recommend_youtube_category(
        self,
        title: str,
        summary: str,
        model: str = "gemini-pro",
        **kwargs
    ) -> str:
        """YouTube 동영상 카테고리 추천"""
        if not self.is_available():
            raise Exception("Google provider is not available.")
            
        try:
            logger.bind(ai=True).info(f"Recommending YouTube category with Google for video: {title[:50]}...")
            
            prompt = f"""다음 YouTube 동영상의 제목과 요약을 분석하여 가장 적합한 카테고리를 추천해주세요.
카테고리는 다음 중 하나여야 합니다:
Education, Entertainment, Technology, Music, Gaming, Sports, News, Lifestyle, Tutorial, Review, Vlog, Comedy, Science, Business, Art

제목: {title}
요약: {summary}

카테고리명만 응답해주세요."""
            
            gemini_model = self._genai.GenerativeModel(model)
            generation_config = self._genai.types.GenerationConfig(
                max_output_tokens=50,
                temperature=0.3
            )
            
            response = await gemini_model.generate_content_async(
                prompt,
                generation_config=generation_config
            )
            
            category = response.text.strip()
            
            logger.bind(ai=True).info(f"YouTube category recommended with Google: {category}")
            return category
            
        except Exception as e:
            logger.error(f"Failed to recommend YouTube category with Google: {str(e)}")
            raise Exception(f"Google API 호출 중 오류: {str(e)}")
    
    def count_tokens(self, text: str, model: str) -> int:
        """텍스트의 토큰 수 계산 (Google은 대략적으로 OpenAI 토크나이저 사용)"""
        try:
            # Gemini 모델에 따른 토큰 계산은 복잡하므로 임시로 OpenAI 토크나이저 사용
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"Failed to count tokens for Google, using character-based estimation: {e}")
            # Fallback: 대략 1 토큰 = 4 문자로 추정
            return len(text) // 4