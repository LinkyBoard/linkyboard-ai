"""AI 도메인 리포지토리
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.datetime import now_utc
from app.domains.ai.models import ModelCatalog, SummaryCache


class AIRepository:
    """AI 리포지토리"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_summary_cache(
        self, cache_key: str
    ) -> Optional[SummaryCache]:
        """캐시 키로 요약 캐시 조회

        Args:
            cache_key: 캐시 키

        Returns:
            SummaryCache 객체 또는 None
        """
        query = select(SummaryCache).where(
            SummaryCache.cache_key == cache_key,
            SummaryCache.expires_at > now_utc(),
        )
        result = await self.session.execute(query)
        cache: Optional[SummaryCache] = result.scalar_one_or_none()
        return cache

    async def get_model_by_alias(self, alias: str) -> Optional[ModelCatalog]:
        """모델 별칭으로 모델 정보 조회

        Args:
            alias: 모델 별칭 (예: gpt-4o-mini, claude-4.5-haiku)

        Returns:
            ModelCatalog 객체 또는 None
        """
        query = select(ModelCatalog).where(
            ModelCatalog.alias == alias,
            ModelCatalog.is_available == True,  # noqa: E712
        )
        result = await self.session.execute(query)
        model: Optional[ModelCatalog] = result.scalar_one_or_none()
        return model

    async def get_all_models(self) -> list[ModelCatalog]:
        """사용 가능한 모든 모델 조회

        Returns:
            ModelCatalog 객체 리스트
        """
        query = (
            select(ModelCatalog)
            .where(ModelCatalog.is_available == True)  # noqa: E712
            .order_by(ModelCatalog.provider, ModelCatalog.alias)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_models_by_tier(self, tier: str) -> list[ModelCatalog]:
        """티어별 fallback 모델 조회 (우선순위 순)

        Args:
            tier: LLM 티어 (light, standard, premium, search, embedding)

        Returns:
            fallback_priority 순으로 정렬된 ModelCatalog 객체 리스트
        """
        query = (
            select(ModelCatalog)
            .where(
                ModelCatalog.tier == tier,
                ModelCatalog.is_available == True,  # noqa: E712
                ModelCatalog.fallback_priority.isnot(None),
            )
            .order_by(ModelCatalog.fallback_priority)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
