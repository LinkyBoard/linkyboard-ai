"""검색 리포지토리

벡터 검색, 키워드 검색, 하이브리드 검색 쿼리를 담당합니다.
"""

from typing import Any, Optional

from sqlalchemy import Float, and_, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domains.ai.models import ContentEmbeddingMetadata
from app.domains.ai.search.types import SearchFilters
from app.domains.contents.models import Content

logger = get_logger(__name__)


class AISearchRepository:
    """검색 전용 리포지토리

    pgvector 벡터 검색 및 PostgreSQL Full-Text Search를 지원합니다.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    def _build_filters(self, filters: Optional[SearchFilters]) -> list:
        """공통 필터 조건 생성

        Args:
            filters: 검색 필터

        Returns:
            list: SQLAlchemy filter 조건 리스트
        """
        conditions: list[Any] = []

        if not filters:
            return conditions

        # content_type 필터 (IN 조건)
        if filters.content_type:
            conditions.append(Content.content_type.in_(filters.content_type))

        # category 필터
        if filters.category:
            conditions.append(Content.category == filters.category)

        # tags 필터 (배열 오버랩 - 하나라도 일치하면 선택)
        if filters.tags:
            # PostgreSQL ARRAY overlap operator: tags && ARRAY['tag1', 'tag2']
            conditions.append(Content.tags.overlap(filters.tags))

        # date_from 필터
        if filters.date_from:
            conditions.append(Content.created_at >= filters.date_from)

        # date_to 필터
        if filters.date_to:
            conditions.append(Content.created_at <= filters.date_to)

        return conditions

    async def vector_search(
        self,
        query_embedding: list[float],
        user_id: int,
        filters: Optional[SearchFilters] = None,
        page: int = 1,
        size: int = 20,
        threshold: float = 0.5,
    ) -> tuple[list[dict], int]:
        """벡터 유사도 검색

        pgvector의 코사인 거리 연산자 (<=>)를 사용하여
        임베딩 벡터 간 유사도를 계산합니다.

        Args:
            query_embedding: 쿼리 임베딩 벡터 (3072 차원)
            user_id: 사용자 ID
            filters: 검색 필터
            page: 페이지 번호 (1부터 시작)
            size: 페이지 크기
            threshold: 최소 유사도 임계값 (0.0~1.0)

        Returns:
            tuple[list[dict], int]: (검색 결과, 전체 개수)
                검색 결과:
                - content_id: int
                - title: str
                - summary: str
                - content_type: str
                - source_url: str
                - similarity: float (0.0~1.0)
                - chunk_content: str (매칭된 청크)
                - chunk_index: int

        Note:
            pgvector <=> 연산자는 코사인 거리를 반환 (0에 가까울수록 유사)
            similarity = 1 - cosine_distance
        """
        # 벡터를 PostgreSQL array literal로 변환
        vector_literal = f"[{','.join(map(str, query_embedding))}]"

        # 기본 필터 조건
        filter_conditions = [
            Content.user_id == user_id,
            Content.deleted_at.is_(None),
            Content.embedding_status == "completed",
        ]

        # 추가 필터 적용
        filter_conditions.extend(self._build_filters(filters))

        # 유사도 조건 (threshold)
        similarity_expr = 1 - cast(
            ContentEmbeddingMetadata.embedding_vector.op("<=>")(
                text(f"'{vector_literal}'::vector")
            ),
            Float(),
        )

        # 전체 개수 조회 (페이지네이션용)
        count_query = (
            select(func.count(func.distinct(Content.id)))
            .select_from(Content)
            .join(
                ContentEmbeddingMetadata,
                ContentEmbeddingMetadata.content_id == Content.id,
            )
            .where(and_(*filter_conditions))
            .where(similarity_expr > threshold)
        )
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # 페이지네이션 계산
        offset = (page - 1) * size

        # pgvector 유사도 검색 쿼리
        # 1 - (vector <=> query) = similarity score
        query = (
            select(
                Content.id.label("content_id"),
                Content.title,
                Content.summary,
                Content.content_type,
                Content.source_url,
                similarity_expr.label("similarity"),
                ContentEmbeddingMetadata.chunk_content,
                ContentEmbeddingMetadata.chunk_index,
            )
            .join(
                ContentEmbeddingMetadata,
                ContentEmbeddingMetadata.content_id == Content.id,
            )
            .where(and_(*filter_conditions))
            .where(similarity_expr > threshold)
            .order_by(text("similarity DESC"))
            .offset(offset)
            .limit(size)
        )

        result = await self.session.execute(query)
        rows = result.mappings().all()

        logger.info(
            f"Vector search: query_dim={len(query_embedding)}, "
            f"user_id={user_id}, page={page}, size={size}, "
            f"found={len(rows)}/{total} results"
        )

        return [dict(row) for row in rows], total

    async def keyword_search(
        self,
        query: str,
        user_id: int,
        filters: Optional[SearchFilters] = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict], int]:
        """키워드 검색 (PostgreSQL Full-Text Search)

        title, summary, memo, content_type, source_url, category, tags 를
        하나의 텍스트로 합쳐서 전문 검색을 수행합니다.

        Args:
            query: 검색 쿼리 문자열
            user_id: 사용자 ID
            filters: 검색 필터
            page: 페이지 번호 (1부터 시작)
            size: 페이지 크기

        Returns:
            tuple[list[dict], int]: (검색 결과, 전체 개수)
                검색 결과:
                - content_id: int
                - title: str
                - summary: str
                - content_type: str
                - source_url: str
                - rank: float (relevance score)

        Note:
            - to_tsvector: 텍스트를 검색 가능한 tsvector로 변환
            - plainto_tsquery: 쿼리를 tsquery로 변환 (평문)
            - ts_rank: 관련도 점수 계산
            - 'simple' 언어 설정으로 한/영 혼용 텍스트 처리

        TODO:
            - 다국어 지원 시 언어별 tsvector 처리 고려
            - 매칭 키워드 많은 경우 더 높은 점수 (title, tags 등 가중치 부여)
            - raw content 필드도 포함 고려 (대용량 주의)
        """
        # 기본 필터 조건
        filter_conditions = [
            Content.user_id == user_id,
            Content.deleted_at.is_(None),
        ]

        # 추가 필터 적용
        filter_conditions.extend(self._build_filters(filters))

        # Full-Text Search 쿼리
        # COALESCE로 NULL 처리 (summary가 NULL일 수 있음)
        # TODO : 다국어 지원 시 언어별 tsvector 처리 고려 (한글, 영어 혼용)
        # → 현재는 'simple' 설정으로 한/영 혼용 텍스트를 단순 토큰화하여 처리
        tsvector_expr = func.to_tsvector(
            "simple",
            func.coalesce(Content.title, "")
            + " "
            + func.coalesce(Content.summary, "")
            + " "
            + func.coalesce(Content.content_type, "")
            + " "
            + func.coalesce(Content.source_url, "")
            + " "
            + func.coalesce(Content.memo, "")
            + " "
            + func.coalesce(Content.category, "")
            + " "
            + func.coalesce(func.array_to_string(Content.tags, " "), ""),
        )
        tsquery_expr = func.plainto_tsquery("simple", query)

        # FTS 매칭 조건
        fts_condition = tsvector_expr.op("@@")(tsquery_expr)

        # 전체 개수 조회 (페이지네이션용)
        count_query = (
            select(func.count(Content.id))
            .select_from(Content)
            .where(and_(*filter_conditions))
            .where(fts_condition)
        )
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # 페이지네이션 계산
        offset = (page - 1) * size

        query_stmt = (
            select(
                Content.id.label("content_id"),
                Content.title,
                Content.summary,
                Content.content_type,
                Content.source_url,
                func.ts_rank(tsvector_expr, tsquery_expr).label("rank"),
            )
            .where(and_(*filter_conditions))
            .where(fts_condition)
            .order_by(text("rank DESC"))
            .offset(offset)
            .limit(size)
        )

        result = await self.session.execute(query_stmt)
        rows = result.mappings().all()

        logger.info(
            f"Keyword search: query='{query}', "
            f"user_id={user_id}, page={page}, size={size}, "
            f"found={len(rows)}/{total} results"
        )

        return [dict(row) for row in rows], total

    async def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        user_id: int,
        filters: Optional[SearchFilters] = None,
        page: int = 1,
        size: int = 20,
        alpha: float = 0.7,
        threshold: float = 0.5,
    ) -> tuple[list[dict], int]:
        """하이브리드 검색 (벡터 + 키워드 결합)

        벡터 검색과 키워드 검색 결과를 결합하여 최종 스코어를 계산합니다.

        Args:
            query: 검색 쿼리 문자열
            query_embedding: 쿼리 임베딩 벡터
            user_id: 사용자 ID
            filters: 검색 필터
            page: 페이지 번호 (1부터 시작)
            size: 페이지 크기
            alpha: 벡터 검색 가중치 (0.0~1.0, 기본 0.7)
            threshold: 벡터 검색 최소 유사도 임계값

        Returns:
            tuple[list[dict], int]: (검색 결과, 전체 개수)
                검색 결과:
                - content_id: int
                - title: str
                - summary: str
                - content_type: str
                - source_url: str
                - final_score: float (하이브리드 스코어)
                - vector_score: float (벡터 유사도)
                - keyword_score: float (키워드 관련도)

        Note:
            final_score =
                (vector_score * alpha) + (keyword_score * (1 - alpha))
            중복 콘텐츠는 content_id로 병합
        """
        # 벡터 검색과 키워드 검색을 충분히 가져옴 (병합을 위해)
        # 최소 페이지 * 크기 * 2, 최대 100개
        fetch_limit = min(page * size * 2, 100)

        # 벡터 검색 결과
        vector_results, _ = await self.vector_search(
            query_embedding=query_embedding,
            user_id=user_id,
            filters=filters,
            page=1,
            size=fetch_limit,
            threshold=threshold,
        )

        # 키워드 검색 결과
        keyword_results, _ = await self.keyword_search(
            query=query,
            user_id=user_id,
            filters=filters,
            page=1,
            size=fetch_limit,
        )

        # 결과 병합 (content_id를 키로 사용)
        merged_results: dict[int, dict] = {}

        # 벡터 검색 결과 추가
        for result in vector_results:
            content_id = result["content_id"]
            merged_results[content_id] = {
                "content_id": content_id,
                "title": result["title"],
                "summary": result["summary"],
                "content_type": result["content_type"],
                "source_url": result["source_url"],
                "vector_score": result["similarity"],
                "keyword_score": 0.0,
            }

        # 키워드 검색 결과 병합
        # 정규화: rank를 0~1 범위로 변환
        max_rank = (
            max((r["rank"] for r in keyword_results), default=1.0) or 1.0
        )

        for result in keyword_results:
            content_id = result["content_id"]
            normalized_rank = result["rank"] / max_rank

            if content_id in merged_results:
                # 기존 벡터 결과에 키워드 점수 추가
                merged_results[content_id]["keyword_score"] = normalized_rank
            else:
                # 키워드만 매칭된 경우
                merged_results[content_id] = {
                    "content_id": content_id,
                    "title": result["title"],
                    "summary": result["summary"],
                    "content_type": result["content_type"],
                    "source_url": result["source_url"],
                    "vector_score": 0.0,
                    "keyword_score": normalized_rank,
                }

        # 하이브리드 스코어 계산
        for data in merged_results.values():
            data["final_score"] = (data["vector_score"] * alpha) + (
                data["keyword_score"] * (1 - alpha)
            )

        # final_score로 정렬
        sorted_results = sorted(
            merged_results.values(),
            key=lambda x: x["final_score"],
            reverse=True,
        )

        # 전체 개수
        total = len(sorted_results)

        # 페이지네이션 적용
        offset = (page - 1) * size
        final_results = sorted_results[offset : offset + size]

        logger.info(
            f"Hybrid search: query='{query}', "
            f"user_id={user_id}, page={page}, size={size}, "
            f"vector_count={len(vector_results)}, "
            f"keyword_count={len(keyword_results)}, "
            f"merged_total={total}, returned={len(final_results)} results"
        )

        return final_results, total
