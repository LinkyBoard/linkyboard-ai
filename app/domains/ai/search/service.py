"""AI 검색 서비스
"""
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import create_embedding
from app.core.logging import get_logger
from app.domains.ai.search.repository import AISearchRepository
from app.domains.ai.search.types import SearchFilters

logger = get_logger(__name__)


class AISearchService:
    """AI 검색 서비스"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = AISearchRepository(session)

    async def search(
        self,
        query: str,
        user_id: int,
        mode: str = "hybrid",  # vector, keyword, hybrid
        filters: Optional[SearchFilters] = None,
        page: int = 1,
        size: int = 20,
        threshold: float = 0.5,
        include_chunks: bool = False,
    ) -> tuple[list[dict], int]:
        """통합 검색

        1. 검색 모드에 따라 실행:
            - vector: 벡터 검색만
            - keyword: 키워드 검색만
            - hybrid: 하이브리드 검색

        2. 벡터 검색 시:
            - 쿼리 임베딩 생성
            - vector_search 호출

        3. 결과 구성:
            - Content 정보 포함
            - 스코어 포함 (similarity, rank, final_score)
            - include_chunks=true 시 매칭된 청크 포함

        Returns:
            (검색 결과, 총 개수)
        """
        results: list[dict[str, Any]] = []
        total = 0

        if mode == "vector":
            # 쿼리 임베딩 생성
            logger.info(f"Creating embedding for query: '{query}'")
            query_embedding = await create_embedding(query, self.session)

            results, total = await self.repository.vector_search(
                query_embedding=query_embedding,
                user_id=user_id,
                filters=filters,
                page=page,
                size=size,
                threshold=threshold,
            )

            # include_chunks가 False이면 청크 정보 제거
            if not include_chunks:
                for result in results:
                    result.pop("chunk_content", None)
                    result.pop("chunk_index", None)

        elif mode == "keyword":
            results, total = await self.repository.keyword_search(
                query=query,
                user_id=user_id,
                filters=filters,
                page=page,
                size=size,
            )

        elif mode == "hybrid":
            # 쿼리 임베딩 생성
            logger.info(f"Creating embedding for query: '{query}'")
            query_embedding = await create_embedding(query, self.session)

            results, total = await self.repository.hybrid_search(
                query=query,
                query_embedding=query_embedding,
                user_id=user_id,
                filters=filters,
                page=page,
                size=size,
                threshold=threshold,
            )

        else:
            raise ValueError(f"Invalid search mode: {mode}")

        logger.info(
            f"Search completed: mode={mode}, query='{query}', "
            f"user_id={user_id}, found={len(results)}/{total} results"
        )

        return results, total
