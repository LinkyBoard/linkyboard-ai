import openai
from typing import List, Dict, Any
from app.core.config import settings
from app.core.logging import get_logger
from app.metrics import count_tokens, record_llm_usage
from app.observability import trace_ai_operation, record_ai_tokens, record_wtu_usage

logger = get_logger(__name__)


class OpenAIService:
    """OpenAI API 연동 서비스"""
    
    def __init__(self, api_key: str):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        logger.info("OpenAI service initialized")

    async def generate_youtube_summary(
        self, 
        title: str,
        transcript: str,
        user_id: int = None
    ) -> str:
        """유튜브 동영상 요약 생성"""
        try:
            logger.bind(ai=True).info(f"Generating YouTube summary for video: {title[:50]}...")
            
            prompt = f"""
            다음 YouTube 동영상의 제목과 스크립트를 분석하여 핵심 내용을 요약해주세요.
            요약은 동영상의 주요 내용, 핵심 메시지, 중요한 정보를 포함해야 합니다.
            요약은 한국어로 작성하고, 3-5문장으로 간결하게 작성해주세요.

            제목: {title}
            
            스크립트:
            {transcript[:3000]}  # 스크립트가 너무 길면 처음 3000자만 사용
            """
            
            system_msg = "당신은 YouTube 동영상 콘텐츠를 분석하는 전문가입니다."
            
            # 토큰 수 계산
            input_tokens = count_tokens(system_msg + prompt, settings.OPENAI_MODEL)
            
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            summary = response.choices[0].message.content.strip()
            output_tokens = response.usage.completion_tokens
            
            # 토큰 사용량 기록
            record_ai_tokens(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=settings.OPENAI_MODEL
            )
            
            # WTU 사용량 기록
            if user_id:
                record_wtu_usage(
                    user_id=user_id,
                    model=settings.OPENAI_MODEL,
                    wtu_amount=input_tokens + output_tokens
                )
            
            logger.bind(ai=True).info(f"YouTube summary generated successfully (length: {len(summary)})")
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate YouTube summary: {str(e)}")
            raise

    async def generate_youtube_tags(
        self, 
        title: str,
        summary: str,
        tag_count: int = 5,
        user_id: int = None
    ) -> List[str]:
        """유튜브 동영상 태그 생성"""
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
            
            input_tokens = count_tokens(system_msg + prompt, settings.OPENAI_MODEL)
            
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=100
            )
            
            tags_text = response.choices[0].message.content.strip()
            output_tokens = response.usage.completion_tokens
            
            # 태그 파싱
            tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
            
            # 토큰 사용량 기록
            record_ai_tokens(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=settings.OPENAI_MODEL
            )
            
            if user_id:
                record_wtu_usage(
                    user_id=user_id,
                    model=settings.OPENAI_MODEL,
                    wtu_amount=input_tokens + output_tokens
                )
            
            logger.bind(ai=True).info(f"YouTube tags generated: {tags}")
            return tags
            
        except Exception as e:
            logger.error(f"Failed to generate YouTube tags: {str(e)}")
            raise

    async def recommend_youtube_category(
        self, 
        title: str,
        summary: str,
        user_id: int = None
    ) -> str:
        """유튜브 동영상 카테고리 추천"""
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
            
            input_tokens = count_tokens(system_msg + prompt, settings.OPENAI_MODEL)
            
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=50
            )
            
            category = response.choices[0].message.content.strip()
            output_tokens = response.usage.completion_tokens
            
            # 토큰 사용량 기록
            record_ai_tokens(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=settings.OPENAI_MODEL
            )
            
            if user_id:
                record_wtu_usage(
                    user_id=user_id,
                    model=settings.OPENAI_MODEL,
                    wtu_amount=input_tokens + output_tokens
                )
            
            logger.bind(ai=True).info(f"YouTube category recommended: {category}")
            return category
            
        except Exception as e:
            logger.error(f"Failed to recommend YouTube category: {str(e)}")
            raise

    async def generate_webpage_tags(
        self, 
        summary: str,
        similar_tags: List[str] = None,
        tag_count: int = 5,
        max_tokens: int = 100,
        user_id: int = None  # WTU 계측을 위한 사용자 ID
    ) -> List[str]:
        """웹페이지 태그 생성 (WTU 계측 + 관측성 포함)"""
        async with trace_ai_operation(
            model=settings.OPENAI_MODEL, 
            operation="tag_generation",
            summary_length=len(summary),
            tag_count=tag_count,
            user_id=user_id or "unknown"
        ) as span:
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
                
                # 토큰 수 계산 (요청 전)
                input_tokens = count_tokens(system_msg + prompt, settings.OPENAI_MODEL)
                logger.bind(ai=True).info(f"Estimated input tokens: {input_tokens}")
                span.set_attribute("ai.input_tokens", input_tokens)
                
                response = await self.client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=max_tokens,
                    temperature=0.3
                )
                
                content = response.choices[0].message.content
                tags = [k.strip() for k in content.split(',') if k.strip()]
                
                # 출력 토큰 수 계산
                output_tokens = count_tokens(content, settings.OPENAI_MODEL)
                span.set_attribute("ai.output_tokens", output_tokens)
                span.set_attribute("ai.tags_generated", len(tags))
                
                # 관측성 메트릭 기록
                record_ai_tokens(settings.OPENAI_MODEL, input_tokens=input_tokens, output_tokens=output_tokens)
                
                # WTU 사용량 기록 (user_id가 있을 때만)
                if user_id:
                    try:
                        await record_llm_usage(
                            user_id=user_id,
                            in_tokens=input_tokens,
                            out_tokens=output_tokens,
                            llm_model=settings.OPENAI_MODEL
                        )
                        # WTU도 관측성 메트릭에 기록
                        from app.metrics import calculate_wtu
                        wtu_amount, _ = await calculate_wtu(
                            in_tokens=input_tokens, 
                            out_tokens=output_tokens, 
                            llm_model=settings.OPENAI_MODEL
                        )
                        record_wtu_usage(user_id, settings.OPENAI_MODEL, wtu_amount)
                        span.set_attribute("ai.wtu_consumed", wtu_amount)
                        
                        logger.bind(ai=True).info(f"WTU usage recorded for user {user_id}: {input_tokens} input + {output_tokens} output tokens = {wtu_amount} WTU")
                    except Exception as wtu_error:
                        # WTU 기록 실패는 태그 생성을 방해하지 않음
                        logger.bind(ai=True).warning(f"Failed to record WTU usage: {wtu_error}")
                
                logger.bind(ai=True).info(f"Generated {len(tags)} tags: {tags}")
                return tags
                
            except Exception as e:
                span.set_attribute("ai.error", str(e))
                logger.bind(ai=True).error(f"Failed to generate tags: {str(e)}")
                raise Exception(f"OpenAI API 호출 중 오류: {str(e)}")

    async def recommend_webpage_category(
        self,
        summary: str,
        similar_categories: List[str] = None,
        max_tokens: int = 100,
        user_id: int = None  # WTU 계측을 위한 사용자 ID
    ) -> str:
        """웹페이지 카테고리 추천 (WTU 계측 포함)"""
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
            
            # 토큰 수 계산 (요청 전)
            input_tokens = count_tokens(system_msg + prompt, settings.OPENAI_MODEL)
            logger.bind(ai=True).info(f"Estimated input tokens: {input_tokens}")
            
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )
            
            content = response.choices[0].message.content.strip()
            
            # 출력 토큰 수 계산
            output_tokens = count_tokens(content, settings.OPENAI_MODEL)
            
            # WTU 사용량 기록 (user_id가 있을 때만)
            if user_id:
                try:
                    await record_llm_usage(
                        user_id=user_id,
                        in_tokens=input_tokens,
                        out_tokens=output_tokens,
                        llm_model=settings.OPENAI_MODEL
                    )
                    logger.bind(ai=True).info(f"WTU usage recorded for user {user_id}: {input_tokens} input + {output_tokens} output tokens")
                except Exception as wtu_error:
                    # WTU 기록 실패는 카테고리 추천을 방해하지 않음
                    logger.bind(ai=True).warning(f"Failed to record WTU usage: {wtu_error}")
            
            logger.bind(ai=True).info(f"Recommended category: {content}")
            return content
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to recommend category: {str(e)}")
            raise Exception(f"OpenAI API 호출 중 오류: {str(e)}")

    async def generate_webpage_summary(
        self,
        url: str,
        html_content: str,
        max_tokens: int = 500
    ) -> Dict[str, Any]:
        """웹페이지 요약 생성"""
        try:
            # text_content = self._extract_text_from_html(html_content)
            # NOTE: 현재는 url을 사용해서 openai에서 요약을 생성
            # 이후에 html_content를 사용해서 요약을 생성할 수 있도록 변경 예정
            logger.bind(ai=True).info("Generating summary for URL = %s", url)

            prompt = f"""
            다음 웹페이지 내용을 분석하여 요약을 생성해주세요.
            바로 저장할 수 있도록 요약만 작성해주세요.
            
            URL: {url}
            """
            
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
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

    async def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        user_id: int = None,
        board_id: int = None
    ) -> Dict[str, Any]:
        """
        일반적인 채팅 완성 생성 (Model Picker v1용)
        
        Args:
            messages: 채팅 메시지 리스트 [{"role": "user", "content": "..."}]
            model: 사용할 모델명 (기본값: settings.OPENAI_MODEL)
            max_tokens: 최대 출력 토큰 수
            temperature: 창의성 정도 (0.0~1.0)
            user_id: 사용자 ID (WTU 계측용)
            board_id: 보드 ID (정책 추적용)
            
        Returns:
            {
                "content": "AI 응답 내용",
                "input_tokens": 입력 토큰 수,
                "output_tokens": 출력 토큰 수,
                "model_used": "실제 사용된 모델명"
            }
        """
        if not model:
            model = settings.OPENAI_MODEL
            
        async with trace_ai_operation(
            model=model,
            operation="chat_completion",
            user_id=user_id or "unknown",
            board_id=board_id or "unknown"
        ) as span:
            try:
                logger.bind(ai=True).info(f"Generating chat completion with model: {model}")
                
                # 입력 토큰 수 계산
                full_prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
                input_tokens = count_tokens(full_prompt, model)
                logger.bind(ai=True).info(f"Estimated input tokens: {input_tokens}")
                span.set_attribute("ai.input_tokens", input_tokens)
                span.set_attribute("ai.model", model)
                
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                
                content = response.choices[0].message.content
                output_tokens = count_tokens(content, model)
                
                span.set_attribute("ai.output_tokens", output_tokens)
                span.set_attribute("ai.response_length", len(content))
                
                # 관측성 메트릭 기록
                record_ai_tokens(model, input_tokens=input_tokens, output_tokens=output_tokens)
                
                # WTU 사용량 기록 (user_id가 있을 때만)
                if user_id:
                    try:
                        await record_llm_usage(
                            user_id=user_id,
                            in_tokens=input_tokens,
                            out_tokens=output_tokens,
                            llm_model=model,
                            board_id=board_id
                        )
                        
                        # WTU 계산 및 기록
                        from app.metrics import calculate_wtu
                        wtu_amount, _ = await calculate_wtu(
                            in_tokens=input_tokens,
                            out_tokens=output_tokens,
                            llm_model=model
                        )
                        record_wtu_usage(user_id, model, wtu_amount)
                        span.set_attribute("ai.wtu_consumed", wtu_amount)
                        
                        logger.bind(ai=True).info(f"WTU usage recorded for user {user_id}: {input_tokens} input + {output_tokens} output tokens = {wtu_amount} WTU")
                    except Exception as wtu_error:
                        logger.bind(ai=True).warning(f"Failed to record WTU usage: {wtu_error}")
                
                logger.bind(ai=True).info(f"Generated chat completion: {len(content)} chars")
                
                return {
                    "content": content,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "model_used": model
                }
                
            except Exception as e:
                span.set_attribute("ai.error", str(e))
                logger.bind(ai=True).error(f"Failed to generate chat completion: {str(e)}")
                raise Exception(f"OpenAI API 호출 중 오류: {str(e)}")
    
    def _extract_text_from_html(self, html_content: str) -> str:
        """HTML에서 텍스트 추출"""
        import re
        text = re.sub(r'<[^>]+>', '', html_content)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    async def _generate_embedding(self, content: str) -> List[float]:
        """임베딩 생성"""
        try:
            logger.bind(ai=True).info("Generating embedding for web content")
            
            response = await self.client.embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL,
                input=content
            )
            
            embedding = response.data[0].embedding
            logger.bind(ai=True).info(f"Generated embedding of length {len(embedding)}")
            return embedding
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to generate embedding: {str(e)}")
            raise Exception(f"OpenAI API 호출 중 오류: {str(e)}")

    async def generate_webpage_embedding(self, html_content: str) -> List[float]:
        """웹페이지 HTML 콘텐츠에 대한 임베딩 생성"""
        try:
            logger.bind(ai=True).info("Generating embedding for webpage HTML content")
            contents = self._extract_text_from_html(html_content)
            return await self._generate_embedding(contents)
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to generate webpage embedding: {str(e)}")
            raise Exception(f"OpenAI API 호출 중 오류: {str(e)}")


# 서비스 인스턴스 생성
openai_service = OpenAIService(api_key=settings.OPENAI_API_KEY)
