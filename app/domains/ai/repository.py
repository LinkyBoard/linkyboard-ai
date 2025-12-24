"""AI 도메인 리포지토리
"""

from datetime import timedelta
from typing import Optional

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.datetime import now_utc
from app.domains.ai.models import ModelCallLog, ModelCatalog, SummaryCache


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

    async def get_model_health_stats(
        self, model_alias: Optional[str] = None, hours: int = 24
    ) -> dict:
        """모델 헬스 통계 조회

        Args:
            model_alias: 특정 모델 별칭 (None이면 전체)
            hours: 조회 시간 범위 (기본 24시간)

        Returns:
            dict: {
                "total_calls": int,
                "success_count": int,
                "failed_count": int,
                "fallback_count": int,
                "success_rate": float,
                "avg_response_time_ms": float,
                "error_breakdown": {
                    "RateLimitError": 10,
                    "InsufficientCredits": 5,
                    ...
                }
            }
        """
        cutoff_time = now_utc() - timedelta(hours=hours)

        # 기본 쿼리
        base_query = select(ModelCallLog).where(
            ModelCallLog.created_at >= cutoff_time
        )

        if model_alias:
            base_query = base_query.where(
                ModelCallLog.model_alias == model_alias
            )

        result = await self.session.execute(base_query)
        logs = list(result.scalars().all())

        total_calls = len(logs)
        if total_calls == 0:
            return {
                "total_calls": 0,
                "success_count": 0,
                "failed_count": 0,
                "fallback_count": 0,
                "success_rate": 0.0,
                "avg_response_time_ms": 0.0,
                "error_breakdown": {},
            }

        success_count = sum(1 for log in logs if log.status == "success")
        failed_count = sum(1 for log in logs if log.status == "failed")
        fallback_count = sum(1 for log in logs if log.status == "fallback")

        # 응답 시간 평균
        response_times = [
            log.response_time_ms
            for log in logs
            if log.response_time_ms is not None
        ]
        avg_response_time = (
            sum(response_times) / len(response_times)
            if response_times
            else 0.0
        )

        # 에러 타입별 집계
        error_breakdown: dict[str, int] = {}
        for log in logs:
            if log.error_type:
                error_breakdown[log.error_type] = (
                    error_breakdown.get(log.error_type, 0) + 1
                )

        return {
            "total_calls": total_calls,
            "success_count": success_count,
            "failed_count": failed_count,
            "fallback_count": fallback_count,
            "success_rate": (
                (success_count / total_calls * 100) if total_calls > 0 else 0.0
            ),
            "avg_response_time_ms": avg_response_time,
            "error_breakdown": error_breakdown,
        }

    async def get_tier_health_stats(self, tier: str, hours: int = 24) -> dict:
        """티어별 헬스 통계 조회

        Args:
            tier: LLM 티어
            hours: 조회 시간 범위

        Returns:
            dict: {
                "tier": str,
                "models": [
                    {
                        "alias": str,
                        "total_calls": int,
                        "success_rate": float,
                        "avg_response_time_ms": float
                    },
                    ...
                ]
            }
        """
        cutoff_time = now_utc() - timedelta(hours=hours)

        query = (
            select(
                ModelCallLog.model_alias,
                func.count(ModelCallLog.id).label("total_calls"),
                func.sum(
                    case((ModelCallLog.status == "success", 1), else_=0)
                ).label("success_count"),
                func.avg(ModelCallLog.response_time_ms).label(
                    "avg_response_time"
                ),
            )
            .where(
                ModelCallLog.tier == tier,
                ModelCallLog.created_at >= cutoff_time,
            )
            .group_by(ModelCallLog.model_alias)
        )

        result = await self.session.execute(query)
        rows = result.all()

        models = []
        for row in rows:
            total_calls = row.total_calls or 0
            success_count = row.success_count or 0
            success_rate = (
                (success_count / total_calls * 100) if total_calls > 0 else 0.0
            )

            models.append(
                {
                    "alias": row.model_alias,
                    "total_calls": total_calls,
                    "success_rate": success_rate,
                    "avg_response_time_ms": (
                        float(row.avg_response_time)
                        if row.avg_response_time
                        else 0.0
                    ),
                }
            )

        return {"tier": tier, "models": models}

    async def get_fallback_flows(self, hours: int = 24) -> list[dict]:
        """Fallback 흐름 조회 (source_model → fallback_to)

        Args:
            hours: 조회 시간 범위

        Returns:
            list[dict]: [
                {
                    "source_model": str,
                    "fallback_to": str,
                    "count": int,
                    "error_types": {
                        "RateLimitError": 5,
                        ...
                    }
                },
                ...
            ]
        """
        cutoff_time = now_utc() - timedelta(hours=hours)

        query = select(ModelCallLog).where(
            ModelCallLog.created_at >= cutoff_time,
            ModelCallLog.status == "fallback",
            ModelCallLog.fallback_to.isnot(None),
        )

        result = await self.session.execute(query)
        logs = list(result.scalars().all())

        # fallback 흐름별 집계
        flows: dict[tuple[str, str], dict] = {}
        for log in logs:
            key = (log.model_alias, log.fallback_to)
            if key not in flows:
                flows[key] = {"count": 0, "error_types": {}}

            flows[key]["count"] = flows[key]["count"] + 1

            if log.error_type:
                error_types = flows[key]["error_types"]
                error_types[log.error_type] = (
                    error_types.get(log.error_type, 0) + 1
                )

        # 리스트로 변환
        flow_list = [
            {
                "source_model": source,
                "fallback_to": target,
                "count": data["count"],
                "error_types": data["error_types"],
            }
            for (source, target), data in flows.items()
        ]

        # count 기준 내림차순 정렬
        flow_list.sort(key=lambda x: x["count"], reverse=True)

        return flow_list
