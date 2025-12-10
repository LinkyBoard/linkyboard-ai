"""AI 도메인 리포지토리
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.datetime import now_utc
from app.domains.ai.models import SummaryCache


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
