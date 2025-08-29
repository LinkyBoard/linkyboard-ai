"""
AI Model Router

데이터베이스의 모델 카탈로그를 기반으로 적절한 AI Provider를 선택하고 라우팅합니다.
"""

from typing import Dict, Optional, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from .interface import AIProviderInterface, AIResponse
from .openai_provider import OpenAIProvider
from .claude_provider import ClaudeProvider
from .google_provider import GoogleProvider
from app.core.config import settings
from app.core.logging import get_logger
from app.metrics.model_catalog_service import ModelCatalogService
from app.core.models import ModelCatalog
from app.metrics import record_llm_usage, calculate_wtu
from app.core.utils.observability import trace_ai_operation, record_ai_tokens, record_wtu_usage

logger = get_logger(__name__)


class AIModelRouter:
    """AI 모델 라우터 - 모델별로 적절한 Provider 선택 및 사용량 기록"""
    
    def __init__(self):
        self._providers: Dict[str, AIProviderInterface] = {}
        self._model_catalog_service = ModelCatalogService()
        self._init_providers()
    
    def _init_providers(self):
        """Provider 인스턴스 초기화"""
        # OpenAI Provider
        if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
            self._providers['openai'] = OpenAIProvider(settings.OPENAI_API_KEY)
        
        # Claude Provider  
        if hasattr(settings, 'CLAUDE_API_KEY') and settings.CLAUDE_API_KEY:
            self._providers['claude'] = ClaudeProvider(settings.CLAUDE_API_KEY)
        
        # Google Provider
        if hasattr(settings, 'GOOGLE_API_KEY') and settings.GOOGLE_API_KEY:
            self._providers['google'] = GoogleProvider(settings.GOOGLE_API_KEY)
        
        logger.info(f"Initialized AI providers: {list(self._providers.keys())}")
    
    async def get_provider_for_model(self, model_name: str, session: Optional[AsyncSession] = None) -> tuple[AIProviderInterface, ModelCatalog]:
        """모델명으로 Provider와 모델 카탈로그 정보 조회"""
        
        # 모델 카탈로그에서 모델 정보 조회
        model_catalog = await self._model_catalog_service.get_model_catalog(model_name, session)
        
        if not model_catalog:
            raise ValueError(f"Model '{model_name}' not found in catalog")
        
        provider_name = model_catalog.provider
        if provider_name not in self._providers:
            raise ValueError(f"Provider '{provider_name}' not available or not configured")
        
        provider = self._providers[provider_name]
        if not provider.is_available():
            raise ValueError(f"Provider '{provider_name}' is not available")
        
        return provider, model_catalog
    
    async def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        user_id: Optional[int] = None,
        board_id: Optional[int] = None,
        session: Optional[AsyncSession] = None
    ) -> AIResponse:
        """채팅 완성 생성 (사용량 추적 포함)"""
        
        async with trace_ai_operation(
            model=model,
            operation="chat_completion",
            user_id=user_id or "unknown",
            board_id=board_id or "unknown"
        ) as span:
            try:
                provider, model_catalog = await self.get_provider_for_model(model, session)
                
                span.set_attribute("ai.provider", provider.provider_name)
                span.set_attribute("ai.model", model)
                
                # Provider를 통해 응답 생성
                response = await provider.generate_chat_completion(
                    messages=messages,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                
                # 스팬에 토큰 정보 설정
                span.set_attribute("ai.input_tokens", response.input_tokens)
                span.set_attribute("ai.output_tokens", response.output_tokens)
                span.set_attribute("ai.response_length", len(response.content))
                
                # 관측성 메트릭 기록
                record_ai_tokens(model, input_tokens=response.input_tokens, output_tokens=response.output_tokens)
                
                # WTU 사용량 기록 (user_id가 있을 때만)
                if user_id:
                    await self._record_usage(
                        user_id=user_id,
                        model_catalog=model_catalog,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        board_id=board_id,
                        session=session,
                        span=span
                    )
                
                logger.bind(ai=True).info(f"Chat completion generated via {provider.provider_name}: {len(response.content)} chars")
                return response
                
            except Exception as e:
                span.set_attribute("ai.error", str(e))
                logger.bind(ai=True).error(f"Failed to generate chat completion: {str(e)}")
                raise
    
    async def generate_webpage_tags(
        self,
        summary: str,
        similar_tags: List[str] = None,
        tag_count: int = 5,
        model: str = None,
        user_id: Optional[int] = None,
        session: Optional[AsyncSession] = None,
        **kwargs
    ) -> List[str]:
        """웹페이지 태그 생성"""
        if not model:
            # 기본 모델 사용 (가장 저렴한 모델 우선)
            model = await self._get_default_model("llm", session)
        
        try:
            provider, model_catalog = await self.get_provider_for_model(model, session)
            
            # Provider를 통해 태그 생성
            tags = await provider.generate_webpage_tags(
                summary=summary,
                similar_tags=similar_tags,
                tag_count=tag_count,
                model=model,
                **kwargs
            )
            
            # 사용량 기록 (대략적인 토큰 계산)
            if user_id:
                input_tokens = provider.count_tokens(f"summary: {summary}, tags: {similar_tags}", model)
                output_tokens = provider.count_tokens(", ".join(tags), model)
                
                await self._record_usage(
                    user_id=user_id,
                    model_catalog=model_catalog,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    session=session
                )
            
            logger.bind(ai=True).info(f"Generated {len(tags)} tags via {provider.provider_name}")
            return tags
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to generate tags: {str(e)}")
            raise
    
    async def recommend_webpage_category(
        self,
        summary: str,
        similar_categories: List[str] = None,
        model: str = None,
        user_id: Optional[int] = None,
        session: Optional[AsyncSession] = None,
        **kwargs
    ) -> str:
        """웹페이지 카테고리 추천"""
        if not model:
            model = await self._get_default_model("llm", session)
        
        try:
            provider, model_catalog = await self.get_provider_for_model(model, session)
            
            # Provider를 통해 카테고리 추천
            category = await provider.recommend_webpage_category(
                summary=summary,
                similar_categories=similar_categories,
                model=model,
                **kwargs
            )
            
            # 사용량 기록
            if user_id:
                input_tokens = provider.count_tokens(f"summary: {summary}, categories: {similar_categories}", model)
                output_tokens = provider.count_tokens(category, model)
                
                await self._record_usage(
                    user_id=user_id,
                    model_catalog=model_catalog,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    session=session
                )
            
            logger.bind(ai=True).info(f"Recommended category via {provider.provider_name}: {category}")
            return category
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to recommend category: {str(e)}")
            raise
    
    async def generate_webpage_summary(
        self,
        url: str,
        html_content: str,
        model: str = None,
        max_tokens: int = 500,
        user_id: Optional[int] = None,
        session: Optional[AsyncSession] = None,
        **kwargs
    ) -> str:
        """웹페이지 요약 생성"""
        if not model:
            model = await self._get_default_model("llm", session)
        
        try:
            provider, model_catalog = await self.get_provider_for_model(model, session)
            
            # Provider를 통해 요약 생성
            summary = await provider.generate_webpage_summary(
                url=url,
                html_content=html_content,
                model=model,
                max_tokens=max_tokens,
                **kwargs
            )
            
            # 사용량 기록
            if user_id:
                input_tokens = provider.count_tokens(f"url: {url}", model)
                output_tokens = provider.count_tokens(summary, model)
                
                await self._record_usage(
                    user_id=user_id,
                    model_catalog=model_catalog,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    session=session
                )
            
            logger.bind(ai=True).info(f"Generated summary via {provider.provider_name}: {len(summary)} chars")
            return summary
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to generate summary: {str(e)}")
            raise
    
    async def generate_youtube_summary(
        self,
        title: str,
        transcript: str,
        model: str = None,
        user_id: Optional[int] = None,
        session: Optional[AsyncSession] = None,
        **kwargs
    ) -> str:
        """YouTube 동영상 요약 생성"""
        if not model:
            model = await self._get_default_model("llm", session)
        
        try:
            provider, model_catalog = await self.get_provider_for_model(model, session)
            
            # Provider를 통해 요약 생성
            summary = await provider.generate_youtube_summary(
                title=title,
                transcript=transcript,
                model=model,
                **kwargs
            )
            
            # 사용량 기록
            if user_id:
                input_tokens = provider.count_tokens(f"title: {title}\ntranscript: {transcript[:3000]}", model)
                output_tokens = provider.count_tokens(summary, model)
                
                await self._record_usage(
                    user_id=user_id,
                    model_catalog=model_catalog,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    session=session
                )
            
            logger.bind(ai=True).info(f"Generated YouTube summary via {provider.provider_name}: {len(summary)} chars")
            return summary
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to generate YouTube summary: {str(e)}")
            raise
    
    async def generate_youtube_tags(
        self,
        title: str,
        summary: str,
        tag_count: int = 5,
        model: str = None,
        user_id: Optional[int] = None,
        session: Optional[AsyncSession] = None,
        **kwargs
    ) -> List[str]:
        """YouTube 동영상 태그 생성"""
        if not model:
            model = await self._get_default_model("llm", session)
        
        try:
            provider, model_catalog = await self.get_provider_for_model(model, session)
            
            # Provider를 통해 태그 생성
            tags = await provider.generate_youtube_tags(
                title=title,
                summary=summary,
                tag_count=tag_count,
                model=model,
                **kwargs
            )
            
            # 사용량 기록
            if user_id:
                input_tokens = provider.count_tokens(f"title: {title}\nsummary: {summary}", model)
                output_tokens = provider.count_tokens(", ".join(tags), model)
                
                await self._record_usage(
                    user_id=user_id,
                    model_catalog=model_catalog,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    session=session
                )
            
            logger.bind(ai=True).info(f"Generated YouTube tags via {provider.provider_name}: {tags}")
            return tags
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to generate YouTube tags: {str(e)}")
            raise
    
    async def recommend_youtube_category(
        self,
        title: str,
        summary: str,
        model: str = None,
        user_id: Optional[int] = None,
        session: Optional[AsyncSession] = None,
        **kwargs
    ) -> str:
        """YouTube 동영상 카테고리 추천"""
        if not model:
            model = await self._get_default_model("llm", session)
        
        try:
            provider, model_catalog = await self.get_provider_for_model(model, session)
            
            # Provider를 통해 카테고리 추천
            category = await provider.recommend_youtube_category(
                title=title,
                summary=summary,
                model=model,
                **kwargs
            )
            
            # 사용량 기록
            if user_id:
                input_tokens = provider.count_tokens(f"title: {title}\nsummary: {summary}", model)
                output_tokens = provider.count_tokens(category, model)
                
                await self._record_usage(
                    user_id=user_id,
                    model_catalog=model_catalog,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    session=session
                )
            
            logger.bind(ai=True).info(f"Recommended YouTube category via {provider.provider_name}: {category}")
            return category
            
        except Exception as e:
            logger.bind(ai=True).error(f"Failed to recommend YouTube category: {str(e)}")
            raise
    
    async def _get_default_model(self, model_type: str, session: Optional[AsyncSession] = None) -> str:
        """기본 모델 선택 (비용 효율성 기준)"""
        models = await self._model_catalog_service.get_active_models(model_type, session)
        
        if not models:
            raise ValueError(f"No active {model_type} models found")
        
        # WTU 가중치가 낮은 모델 우선 (비용 효율적)
        default_model = min(models, key=lambda m: (m.weight_input or 1.0) + (m.weight_output or 4.0))
        return default_model.model_name
    
    async def _record_usage(
        self,
        user_id: int,
        model_catalog: ModelCatalog,
        input_tokens: int,
        output_tokens: int,
        board_id: Optional[int] = None,
        session: Optional[AsyncSession] = None,
        span: Optional[Any] = None
    ):
        """사용량 기록"""
        try:
            # WTU 사용량 기록
            await record_llm_usage(
                user_id=user_id,
                in_tokens=input_tokens,
                out_tokens=output_tokens,
                llm_model=model_catalog.model_name,
                board_id=board_id,
                session=session
            )
            
            # WTU 계산 및 관측성 기록
            wtu_amount, _ = await calculate_wtu(
                in_tokens=input_tokens,
                out_tokens=output_tokens,
                llm_model=model_catalog.model_name
            )
            
            record_wtu_usage(user_id, model_catalog.model_name, wtu_amount)
            
            if span:
                span.set_attribute("ai.wtu_consumed", wtu_amount)
            
            logger.bind(ai=True).info(
                f"WTU usage recorded for user {user_id}: {input_tokens} input + {output_tokens} output tokens = {wtu_amount} WTU"
            )
            
        except Exception as wtu_error:
            logger.bind(ai=True).warning(f"Failed to record WTU usage: {wtu_error}")
    
    def get_available_providers(self) -> List[str]:
        """사용 가능한 Provider 목록 반환"""
        return [name for name, provider in self._providers.items() if provider.is_available()]
    
    async def get_available_models(self, model_type: Optional[str] = None, session: Optional[AsyncSession] = None) -> List[Dict[str, Any]]:
        """사용 가능한 모델 목록 반환"""
        models = await self._model_catalog_service.get_active_models(model_type, session)
        
        available_models = []
        for model in models:
            if model.provider in self._providers and self._providers[model.provider].is_available():
                available_models.append({
                    "model_name": model.model_name,
                    "alias": model.alias,
                    "provider": model.provider,
                    "model_type": model.model_type,
                    "input_cost_per_1k": (model.weight_input or 1.0) * 1000,
                    "output_cost_per_1k": (model.weight_output or 4.0) * 1000
                })
        
        return available_models


# 전역 라우터 인스턴스
ai_router = AIModelRouter()