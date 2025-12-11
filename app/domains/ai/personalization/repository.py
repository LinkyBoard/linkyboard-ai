"""개인화 레포지토리

사용자의 태그/카테고리 사용 통계를 조회하고 관리합니다.
"""
from typing import Optional, cast

from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import create_embedding
from app.core.logging import get_logger
from app.core.utils.datetime import now_utc
from app.domains.ai.models import (
    Category,
    Tag,
    UserCategoryUsage,
    UserTagUsage,
)

logger = get_logger(__name__)


class PersonalizationRepository:
    """개인화 레포지토리"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_tag_stats(
        self, user_id: int, limit: int = 50
    ) -> list[dict]:
        """사용자의 태그 사용 통계 조회

        Args:
            user_id: 사용자 ID
            limit: 조회할 최대 태그 수

        Returns:
            태그 사용 통계 리스트 (tag_name, use_count, last_used_at, embedding_vector)
        """
        query = (
            select(
                Tag.tag_name,
                UserTagUsage.use_count,
                UserTagUsage.last_used_at,
                Tag.embedding_vector,
            )
            .join(Tag, UserTagUsage.tag_id == Tag.id)
            .where(UserTagUsage.user_id == user_id)
            .order_by(desc(UserTagUsage.use_count))
            .limit(limit)
        )

        result = await self.session.execute(query)
        rows = result.all()

        return [
            {
                "tag_name": row.tag_name,
                "use_count": row.use_count,
                "last_used_at": row.last_used_at,
                "embedding_vector": row.embedding_vector,
            }
            for row in rows
        ]

    async def get_user_category_stats(
        self, user_id: int, limit: int = 20
    ) -> list[dict]:
        """사용자의 카테고리 사용 통계 조회

        Args:
            user_id: 사용자 ID
            limit: 조회할 최대 카테고리 수

        Returns:
            카테고리 사용 통계 리스트
            (category_name, use_count, last_used_at, embedding_vector)
        """
        query = (
            select(
                Category.category_name,
                UserCategoryUsage.use_count,
                UserCategoryUsage.last_used_at,
                Category.embedding_vector,
            )
            .join(Category, UserCategoryUsage.category_id == Category.id)
            .where(UserCategoryUsage.user_id == user_id)
            .order_by(desc(UserCategoryUsage.use_count))
            .limit(limit)
        )

        result = await self.session.execute(query)
        rows = result.all()

        return [
            {
                "category_name": row.category_name,
                "use_count": row.use_count,
                "last_used_at": row.last_used_at,
                "embedding_vector": row.embedding_vector,
            }
            for row in rows
        ]

    async def get_tag_by_name(self, tag_name: str) -> Optional[Tag]:
        """태그 이름으로 태그 조회

        Args:
            tag_name: 태그 이름

        Returns:
            Tag 객체 또는 None
        """
        query = select(Tag).where(Tag.tag_name == tag_name)
        result = await self.session.execute(query)
        tag = result.scalar_one_or_none()
        return cast(Optional[Tag], tag)

    async def get_category_by_name(
        self, category_name: str
    ) -> Optional[Category]:
        """카테고리 이름으로 카테고리 조회

        Args:
            category_name: 카테고리 이름

        Returns:
            Category 객체 또는 None
        """
        query = select(Category).where(Category.category_name == category_name)
        result = await self.session.execute(query)
        category = result.scalar_one_or_none()
        return cast(Optional[Category], category)

    async def get_global_tag_stats(self, limit: int = 100) -> list[dict]:
        """전체 사용자의 태그 사용 통계 조회 (인기 태그)

        Args:
            limit: 조회할 최대 태그 수

        Returns:
            태그별 전체 사용 횟수 리스트 (tag_name, total_use_count)
        """
        query = (
            select(
                Tag.tag_name,
                func.sum(UserTagUsage.use_count).label("total_use_count"),
            )
            .join(Tag, UserTagUsage.tag_id == Tag.id)
            .group_by(Tag.tag_name)
            .order_by(desc("total_use_count"))
            .limit(limit)
        )

        result = await self.session.execute(query)
        rows = result.all()

        return [
            {
                "tag_name": row.tag_name,
                "total_use_count": row.total_use_count,
            }
            for row in rows
        ]

    async def get_global_category_stats(self, limit: int = 50) -> list[dict]:
        """전체 사용자의 카테고리 사용 통계 조회 (인기 카테고리)

        Args:
            limit: 조회할 최대 카테고리 수

        Returns:
            카테고리별 전체 사용 횟수 리스트 (category_name, total_use_count)
        """
        query = (
            select(
                Category.category_name,
                func.sum(UserCategoryUsage.use_count).label("total_use_count"),
            )
            .join(Category, UserCategoryUsage.category_id == Category.id)
            .group_by(Category.category_name)
            .order_by(desc("total_use_count"))
            .limit(limit)
        )

        result = await self.session.execute(query)
        rows = result.all()

        return [
            {
                "category_name": row.category_name,
                "total_use_count": row.total_use_count,
            }
            for row in rows
        ]

    async def get_or_create_tag(
        self, tag_name: str, embedding_vector: Optional[list[float]] = None
    ) -> Tag:
        """태그 마스터에서 태그 조회 또는 생성

        Args:
            tag_name: 태그 이름
            embedding_vector: 태그 임베딩 벡터 (1536 차원)

        Returns:
            Tag 객체
        """
        # 기존 태그 조회
        existing_tag = await self.get_tag_by_name(tag_name)
        if existing_tag:
            # 임베딩이 없고 새로 제공된 경우 업데이트
            if existing_tag.embedding_vector is None and embedding_vector:
                existing_tag.embedding_vector = embedding_vector
                await self.session.flush()
            return existing_tag

        # 새 태그 생성
        if embedding_vector is None:
            try:
                embedding_vector = await create_embedding(tag_name)
            except Exception:
                # 임베딩 실패 시 None으로 저장 (나중에 재계산)
                embedding_vector = None

        new_tag = Tag(
            tag_name=tag_name,
            embedding_vector=embedding_vector,
            created_at=now_utc(),
        )
        self.session.add(new_tag)
        await self.session.flush()

        logger.info(f"Created new tag: '{tag_name}'")
        return new_tag

    async def get_or_create_category(
        self,
        category_name: str,
        embedding_vector: Optional[list[float]] = None,
    ) -> Category:
        """카테고리 마스터에서 카테고리 조회 또는 생성

        Args:
            category_name: 카테고리 이름
            embedding_vector: 카테고리 임베딩 벡터 (1536 차원)

        Returns:
            Category 객체
        """
        # 기존 카테고리 조회
        existing_category = await self.get_category_by_name(category_name)
        if existing_category:
            # 임베딩이 없고 새로 제공된 경우 업데이트
            if existing_category.embedding_vector is None and embedding_vector:
                existing_category.embedding_vector = embedding_vector
                await self.session.flush()
            return existing_category

        # 새 카테고리 생성
        if embedding_vector is None:
            try:
                embedding_vector = await create_embedding(category_name)
            except Exception:
                embedding_vector = None

        new_category = Category(
            category_name=category_name,
            embedding_vector=embedding_vector,
            created_at=now_utc(),
        )
        self.session.add(new_category)
        await self.session.flush()

        logger.info(f"Created new category: '{category_name}'")
        return new_category

    async def upsert_user_tag_usage(
        self, user_id: int, tag_id: int
    ) -> UserTagUsage:
        """사용자 태그 사용 카운트 증가

        ON CONFLICT DO UPDATE를 사용하여 원자적으로 처리합니다.

        Args:
            user_id: 사용자 ID
            tag_id: 태그 ID

        Returns:
            UserTagUsage 객체
        """
        # PostgreSQL INSERT ... ON CONFLICT DO UPDATE (UPSERT)
        stmt = insert(UserTagUsage).values(
            user_id=user_id,
            tag_id=tag_id,
            use_count=1,
            last_used_at=now_utc(),
        )

        # 중복 시 use_count 증가, last_used_at 갱신
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "tag_id"],
            set_={
                "use_count": UserTagUsage.use_count + 1,
                "last_used_at": now_utc(),
            },
        )

        await self.session.execute(stmt)
        await self.session.flush()

        # 결과 조회
        query = select(UserTagUsage).where(
            UserTagUsage.user_id == user_id,
            UserTagUsage.tag_id == tag_id,
        )
        result = await self.session.execute(query)
        usage = cast(UserTagUsage, result.scalar_one())
        await self.session.refresh(usage)

        logger.debug(
            f"Updated user tag usage: user_id={user_id}, tag_id={tag_id}, "
            f"use_count={usage.use_count}"
        )

        return usage

    async def upsert_user_category_usage(
        self, user_id: int, category_id: int
    ) -> UserCategoryUsage:
        """사용자 카테고리 사용 카운트 증가

        ON CONFLICT DO UPDATE를 사용하여 원자적으로 처리합니다.

        Args:
            user_id: 사용자 ID
            category_id: 카테고리 ID

        Returns:
            UserCategoryUsage 객체
        """
        # PostgreSQL INSERT ... ON CONFLICT DO UPDATE (UPSERT)
        stmt = insert(UserCategoryUsage).values(
            user_id=user_id,
            category_id=category_id,
            use_count=1,
            last_used_at=now_utc(),
        )

        # 중복 시 use_count 증가, last_used_at 갱신
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "category_id"],
            set_={
                "use_count": UserCategoryUsage.use_count + 1,
                "last_used_at": now_utc(),
            },
        )

        await self.session.execute(stmt)
        await self.session.flush()

        # 결과 조회
        query = select(UserCategoryUsage).where(
            UserCategoryUsage.user_id == user_id,
            UserCategoryUsage.category_id == category_id,
        )
        result = await self.session.execute(query)
        usage = cast(UserCategoryUsage, result.scalar_one())

        logger.debug(
            f"Updated user category usage: user_id={user_id}, "
            f"category_id={category_id}, use_count={usage.use_count}"
        )

        return usage
