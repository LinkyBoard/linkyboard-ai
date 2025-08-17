"""
모델별 가격 정보 및 WTU 가중치 관리 서비스

OpenAI 등 AI 모델의 가격 정보를 관리하고,
기준 모델 대비 WTU 가중치를 계산합니다.
"""

import logging
from datetime import datetime
from typing import Optional, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.models import ModelPricing

logger = logging.getLogger(__name__)


class ModelPricingService:
    """모델별 가격 정보 및 WTU 가중치 관리 서비스"""
    
    def __init__(self):
        self._pricing_cache: Dict[str, ModelPricing] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = 3600  # 1시간 캐시
    
    async def get_model_pricing(self, model_name: str, session: Optional[AsyncSession] = None) -> Optional[ModelPricing]:
        """모델의 가격 정보 조회 (캐시 포함)"""
        
        # 캐시 확인
        now = datetime.now()
        if (self._cache_timestamp and 
            (now - self._cache_timestamp).total_seconds() < self._cache_ttl and
            model_name in self._pricing_cache):
            return self._pricing_cache[model_name]
        
        # DB에서 조회
        close_session = False
        if session is None:
            session = AsyncSessionLocal()
            close_session = True
        
        try:
            stmt = select(ModelPricing).where(
                ModelPricing.model_name == model_name,
                ModelPricing.is_active == True
            )
            result = await session.execute(stmt)
            pricing = result.scalar_one_or_none()
            
            # 캐시 업데이트
            if pricing:
                self._pricing_cache[model_name] = pricing
                self._cache_timestamp = now
            
            return pricing
            
        finally:
            if close_session:
                await session.aclose()
    
    async def get_wtu_weights(self, llm_model: Optional[str] = None, embedding_model: Optional[str] = None, 
                             session: Optional[AsyncSession] = None) -> Dict[str, float]:
        """모델별 WTU 가중치 조회"""
        weights = {
            'w_in': 1.0,           # 기본값 (GPT-5 mini 기준)
            'w_cached_in': 0.1,    # 기본값
            'w_out': 8.0,          # 기본값
            'w_embed': 0.064       # 기본값 (text-embedding-3-small 계산값)
        }
        
        # LLM 모델 가중치 조회
        if llm_model:
            llm_pricing = await self.get_model_pricing(llm_model, session)
            if llm_pricing:
                if llm_pricing.weight_input is not None:
                    weights['w_in'] = llm_pricing.weight_input
                    weights['w_cached_in'] = llm_pricing.weight_cached_input
                if llm_pricing.weight_output is not None:
                    weights['w_out'] = llm_pricing.weight_output
        
        # 임베딩 모델 가중치 조회
        if embedding_model:
            embed_pricing = await self.get_model_pricing(embedding_model, session)
            if embed_pricing and embed_pricing.weight_embedding is not None:
                weights['w_embed'] = embed_pricing.weight_embedding
        
        return weights
    
    async def add_or_update_model_pricing(
        self,
        model_name: str,
        model_type: str,
        price_input: Optional[float] = None,
        price_output: Optional[float] = None,
        price_embedding: Optional[float] = None,
        session: Optional[AsyncSession] = None
    ) -> ModelPricing:
        """모델 가격 정보 추가 또는 업데이트"""
        close_session = False
        if session is None:
            session = AsyncSessionLocal()
            close_session = True
        
        try:
            # 기존 레코드 확인
            stmt = select(ModelPricing).where(ModelPricing.model_name == model_name)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                # 기존 레코드 업데이트
                if price_input is not None:
                    existing.price_input = price_input
                if price_output is not None:
                    existing.price_output = price_output
                if price_embedding is not None:
                    existing.price_embedding = price_embedding
                
                existing.calculate_weights()
                pricing = existing
                logger.info(f"Updated pricing for {model_name}")
            else:
                # 새 레코드 생성
                pricing = ModelPricing(
                    model_name=model_name,
                    model_type=model_type,
                    price_input=price_input,
                    price_output=price_output,
                    price_embedding=price_embedding
                )
                pricing.calculate_weights()
                session.add(pricing)
                logger.info(f"Added new pricing for {model_name}")
            
            await session.commit()
            await session.refresh(pricing)
            
            # 캐시 무효화
            if model_name in self._pricing_cache:
                del self._pricing_cache[model_name]
            
            return pricing
            
        finally:
            if close_session:
                await session.aclose()
    
    async def initialize_default_models(self, session: Optional[AsyncSession] = None) -> None:
        """기본 모델들의 가격 정보 초기화"""
        close_session = False
        if session is None:
            session = AsyncSessionLocal()
            close_session = True
        
        try:
            default_models = [
                {
                    'model_name': 'gpt-5-mini',
                    'model_type': 'llm',
                    'price_input': 0.25,
                    'price_output': 2.00,
                },
                {
                    'model_name': 'gpt-3.5-turbo',
                    'model_type': 'llm',
                    'price_input': 0.50,
                    'price_output': 1.50,
                },
                {
                    'model_name': 'text-embedding-3-small',
                    'model_type': 'embedding',
                    'price_embedding': 0.02,
                },
            ]
            
            for model_data in default_models:
                # 이미 존재하는지 확인
                stmt = select(ModelPricing).where(ModelPricing.model_name == model_data['model_name'])
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
                
                if not existing:
                    pricing = ModelPricing(**model_data)
                    pricing.calculate_weights()
                    session.add(pricing)
                    logger.info(f"Added default pricing for {model_data['model_name']}")
            
            await session.commit()
            
        finally:
            if close_session:
                await session.aclose()
    
    def clear_cache(self) -> None:
        """가격 정보 캐시 초기화"""
        self._pricing_cache.clear()
        self._cache_timestamp = None
        logger.info("Cleared pricing cache")


# 전역 서비스 인스턴스
pricing_service = ModelPricingService()
