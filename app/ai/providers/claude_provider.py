"""
Claude Provider 구현

Anthropic Claude API를 사용하여 AI Provider Interface를 구현합니다.
"""

from typing import List, Dict, Any, Optional
import tiktoken

from .interface import AIProviderInterface, AIResponse
from app.core.logging import get_logger

logger = get_logger(__name__)


class ClaudeProvider(AIProviderInterface):
    """Anthropic Claude API Provider"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        try:
            import anthropic
            self.client = anthropic.AsyncAnthropic(api_key=api_key)
            self._anthropic_available = True
            logger.info(f"{self.provider_name} provider initialized")
        except ImportError:
            logger.warning("anthropic package not installed, Claude provider disabled")
            self._anthropic_available = False
            self.client = None
    
    def _get_provider_name(self) -> str:
        return "claude"
    
    def is_available(self) -> bool:
        """Claude provider 사용 가능 여부 확인"""
        return self._anthropic_available and bool(self.api_key)
    
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
            raise Exception("Claude provider is not available. Please install 'anthropic' package.")
        
        try:
            logger.bind(ai=True).info(f"Generating chat completion with Claude model: {model}")
            
            # Claude API 형식으로 메시지 변환
            system_message = ""
            claude_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    claude_messages.append(msg)
            
            # 입력 토큰 수 계산
            full_prompt = system_message + "\n".join([f"{msg['role']}: {msg['content']}" for msg in claude_messages])
            input_tokens = self.count_tokens(full_prompt, model)
            
            response = await self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_message if system_message else None,
                messages=claude_messages
            )
            
            content = response.content[0].text
            output_tokens = self.count_tokens(content, model)
            
            logger.bind(ai=True).info(f"Generated Claude chat completion: {len(content)} chars")
            
            return AIResponse(
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_used=model,
                provider=self.provider_name,
                metadata={"temperature": temperature, "max_tokens": max_tokens}
            )
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to generate Claude chat completion: {str(e)}")
            raise Exception(f"Claude API 호출 중 오류: {str(e)}")
    
    async def generate_webpage_tags(
        self,
        summary: str,
        similar_tags: List[str] = None,
        tag_count: int = 5,
        model: str = "claude-3-haiku-20240307",
        **kwargs
    ) -> List[str]:
        """웹페이지 태그 생성"""
        if not self.is_available():
            raise Exception("Claude provider is not available.")
            
        try:
            logger.bind(ai=True).info(f"Generating tags with Claude for summary (length: {len(summary)})")
            
            prompt = f"""다음 웹페이지 내용을 분석하여 {tag_count}개의 태그를 생성해주세요.
바로 저장할 수 있도록 응답은 태그만 작성해주세요.
각 태그는 쉼표로 구분해주세요.
태그는 한글 또는 영어의 명사형 단어로 작성해주세요.
사용자가 이전에 저장한 유사 태그가 있다면, 그 태그도 함께 고려해주세요.
{', '.join(similar_tags) if similar_tags else '없음'}

summary: {summary}"""
            
            response = await self.client.messages.create(
                model=model,
                max_tokens=kwargs.get('max_tokens', 100),
                temperature=0.3,
                system="당신은 웹페이지 내용을 분석하는 전문가입니다.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            tags = [k.strip() for k in content.split(',') if k.strip()]
            
            logger.bind(ai=True).info(f"Generated {len(tags)} tags with Claude: {tags}")
            return tags
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to generate tags with Claude: {str(e)}")
            raise Exception(f"Claude API 호출 중 오류: {str(e)}")
    
    async def recommend_webpage_category(
        self,
        summary: str,
        similar_categories: List[str] = None,
        model: str = "claude-3-haiku-20240307",
        **kwargs
    ) -> str:
        """웹페이지 카테고리 추천"""
        if not self.is_available():
            raise Exception("Claude provider is not available.")
            
        try:
            logger.bind(ai=True).info(f"Recommending category with Claude for summary (length: {len(summary)})")
            
            prompt = f"""다음 웹페이지 내용을 분석하여 적절한 단 하나의 카테고리를 추천해주세요.
바로 저장할 수 있도록 카테고리만 작성해주세요.
사용자가 이전에 저장한 유사 카테고리가 있다면, 그 카테고리도 함께 고려해주세요.
{', '.join(similar_categories) if similar_categories else '없음'}
카테고리는 반드시 하나여야 하며, 여러 개의 카테고리를 추천하지 마세요.
사용자가 이전에 저장한 카테고리중 적합한게 없다면 새로 추천해주세요.

summary: {summary}"""
            
            response = await self.client.messages.create(
                model=model,
                max_tokens=kwargs.get('max_tokens', 100),
                temperature=0.3,
                system="당신은 웹페이지 내용을 분석하는 전문가입니다.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text.strip()
            
            logger.bind(ai=True).info(f"Recommended category with Claude: {content}")
            return content
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to recommend category with Claude: {str(e)}")
            raise Exception(f"Claude API 호출 중 오류: {str(e)}")
    
    async def generate_webpage_summary(
        self,
        url: str,
        html_content: str,
        model: str = "claude-3-haiku-20240307",
        max_tokens: int = 500,
        **kwargs
    ) -> str:
        """웹페이지 요약 생성"""
        if not self.is_available():
            raise Exception("Claude provider is not available.")
            
        try:
            logger.bind(ai=True).info(f"Generating summary with Claude for URL: {url}")

            prompt = f"""다음 웹페이지 내용을 분석하여 요약을 생성해주세요.
바로 저장할 수 있도록 요약만 작성해주세요.

URL: {url}"""
            
            response = await self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=0.3,
                system="당신은 웹페이지 내용을 분석하는 전문가입니다.",
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text.strip()
            logger.bind(ai=True).info(f"Generated summary with Claude (length: {len(content)})")
            return content
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to generate summary with Claude for {url}: {str(e)}")
            raise Exception(f"Claude API 호출 중 오류: {str(e)}")
    
    async def generate_youtube_summary(
        self,
        title: str,
        transcript: str,
        model: str = "claude-3-haiku-20240307",
        **kwargs
    ) -> str:
        """YouTube 동영상 요약 생성"""
        if not self.is_available():
            raise Exception("Claude provider is not available.")
            
        try:
            logger.bind(ai=True).info(f"Generating YouTube summary with Claude for video: {title[:50]}...")
            
            prompt = f"""다국어 YouTube 비디오 자막 분석 및 한국어 요약 요청

핵심 미션:
아래 비디오의 자막을 완전히 이해한 후, 자연스럽고 유창한 한국어로 요약해주세요.

비디오 정보:
제목: {title}

자막 내용:
{transcript[:3000]}

요약 규칙:
1. 자막이 영어, 일본어, 중국어, 스페인어 등 어떤 언어이든 상관없이 내용을 이해하고 한국어로 다시 작성
2. 3-5문장의 잘 구성된 한국어 요약
3. 동영상의 핵심 내용, 주요 메시지, 중요한 정보를 모두 포함
4. 자연스럽고 읽기 쉬운 한국어 표현

❗ 절대 요구사항: 반드시 한국어로만 작성. 영어나 다른 언어 사용 절대 금지."""
            
            response = await self.client.messages.create(
                model=model,
                max_tokens=500,
                temperature=0.7,
                system="당신은 YouTube 동영상 콘텐츠를 분석하는 전문가입니다.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            summary = response.content[0].text.strip()
            
            logger.bind(ai=True).info(f"YouTube summary generated with Claude (length: {len(summary)})")
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate YouTube summary with Claude: {str(e)}")
            raise Exception(f"Claude API 호출 중 오류: {str(e)}")
    
    async def generate_youtube_tags(
        self,
        title: str,
        summary: str,
        tag_count: int = 5,
        model: str = "claude-3-haiku-20240307",
        **kwargs
    ) -> List[str]:
        """YouTube 동영상 태그 생성"""
        if not self.is_available():
            raise Exception("Claude provider is not available.")
            
        try:
            logger.bind(ai=True).info(f"Generating YouTube tags with Claude for video: {title[:50]}...")
            
            prompt = f"""다음 YouTube 동영상의 제목과 요약을 분석하여 {tag_count}개의 태그를 생성해주세요.
태그는 동영상의 주제, 카테고리, 핵심 키워드를 반영해야 합니다.
각 태그는 쉼표로 구분해주세요.
태그는 한글 또는 영어의 명사형 단어로 작성해주세요.

제목: {title}
요약: {summary}"""
            
            response = await self.client.messages.create(
                model=model,
                max_tokens=100,
                temperature=0.5,
                system="당신은 YouTube 콘텐츠를 분석하는 태그 생성 전문가입니다.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            tags_text = response.content[0].text.strip()
            tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
            
            logger.bind(ai=True).info(f"YouTube tags generated with Claude: {tags}")
            return tags
            
        except Exception as e:
            logger.error(f"Failed to generate YouTube tags with Claude: {str(e)}")
            raise Exception(f"Claude API 호출 중 오류: {str(e)}")
    
    async def recommend_youtube_category(
        self,
        title: str,
        summary: str,
        model: str = "claude-3-haiku-20240307",
        **kwargs
    ) -> str:
        """YouTube 동영상 카테고리 추천"""
        if not self.is_available():
            raise Exception("Claude provider is not available.")
            
        try:
            logger.bind(ai=True).info(f"Recommending YouTube category with Claude for video: {title[:50]}...")
            
            prompt = f"""다음 YouTube 동영상의 제목과 요약을 분석하여 가장 적합한 카테고리를 추천해주세요.
카테고리는 다음 중 하나여야 합니다:
Education, Entertainment, Technology, Music, Gaming, Sports, News, Lifestyle, Tutorial, Review, Vlog, Comedy, Science, Business, Art

제목: {title}
요약: {summary}

카테고리명만 응답해주세요."""
            
            response = await self.client.messages.create(
                model=model,
                max_tokens=50,
                temperature=0.3,
                system="당신은 YouTube 콘텐츠를 분석하는 카테고리 분류 전문가입니다.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            category = response.content[0].text.strip()
            
            logger.bind(ai=True).info(f"YouTube category recommended with Claude: {category}")
            return category
            
        except Exception as e:
            logger.error(f"Failed to recommend YouTube category with Claude: {str(e)}")
            raise Exception(f"Claude API 호출 중 오류: {str(e)}")
    
    def count_tokens(self, text: str, model: str) -> int:
        """텍스트의 토큰 수 계산 (Claude는 대략적으로 OpenAI 토크나이저 사용)"""
        try:
            # Claude 모델에 따른 토큰 계산은 복잡하므로 임시로 OpenAI 토크나이저 사용
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"Failed to count tokens for Claude, using character-based estimation: {e}")
            # Fallback: 대략 1 토큰 = 4 문자로 추정
            return len(text) // 4