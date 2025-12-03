"""Contents 도메인 리포지토리

콘텐츠 CRUD 및 필터링을 위한 데이터 접근 계층입니다.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence, cast

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.datetime import now_utc
from app.domains.contents.models import Content, ContentType, ProcessingStatus


@dataclass
class ContentFilters:
    """콘텐츠 목록 조회 필터

    모든 필드는 선택적이며, 제공된 필터만 적용됩니다.
    """

    content_type: Optional[ContentType] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    processing_status: Optional[ProcessingStatus] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class ContentRepository:
    """콘텐츠 리포지토리"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
        self, content_id: int, include_deleted: bool = False
    ) -> Optional[Content]:
        """ID로 콘텐츠 조회

        Args:
            content_id: 콘텐츠 ID
            include_deleted: 삭제된 콘텐츠 포함 여부 (기본: False)

        Returns:
            콘텐츠 객체 또는 None
        """
        query = select(Content).where(Content.id == content_id)

        if not include_deleted:
            query = query.where(Content.deleted_at.is_(None))

        result = await self.session.execute(query)
        return cast(Optional[Content], result.scalar_one_or_none())

    async def get_by_url(
        self, source_url: str, user_id: int
    ) -> Optional[Content]:
        """URL과 사용자 ID로 콘텐츠 조회 (중복 탐지용)

        Args:
            source_url: 원본 URL
            user_id: 사용자 ID

        Returns:
            콘텐츠 객체 또는 None
        """
        query = select(Content).where(
            and_(
                Content.source_url == source_url,
                Content.user_id == user_id,
                Content.deleted_at.is_(None),
            )
        )

        result = await self.session.execute(query)
        return cast(Optional[Content], result.scalar_one_or_none())

    async def get_by_file_hash(
        self, file_hash: str, user_id: int
    ) -> Optional[Content]:
        """파일 해시와 사용자 ID로 콘텐츠 조회 (PDF 중복 탐지용)

        Args:
            file_hash: 파일 해시 (SHA-256)
            user_id: 사용자 ID

        Returns:
            콘텐츠 객체 또는 None
        """
        query = select(Content).where(
            and_(
                Content.file_hash == file_hash,
                Content.user_id == user_id,
                Content.deleted_at.is_(None),
            )
        )

        result = await self.session.execute(query)
        return cast(Optional[Content], result.scalar_one_or_none())

    async def get_list(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 20,
        filters: Optional[ContentFilters] = None,
    ) -> Sequence[Content]:
        """콘텐츠 목록 조회

        Args:
            user_id: 사용자 ID
            skip: 건너뛸 레코드 수
            limit: 조회할 최대 레코드 수
            filters: 필터 옵션

        Returns:
            콘텐츠 목록
        """
        query = select(Content).where(
            and_(
                Content.user_id == user_id,
                Content.deleted_at.is_(None),
            )
        )

        # 필터 적용
        if filters:
            if filters.content_type:
                query = query.where(
                    Content.content_type == filters.content_type
                )

            if filters.category:
                query = query.where(Content.category == filters.category)

            if filters.tags:
                # PostgreSQL ARRAY에서 ANY 연산자 사용 (OR 로직)
                query = query.where(Content.tags.overlap(filters.tags))

            if filters.processing_status:
                query = query.where(
                    Content.processing_status == filters.processing_status
                )

            if filters.date_from:
                query = query.where(Content.created_at >= filters.date_from)

            if filters.date_to:
                query = query.where(Content.created_at <= filters.date_to)

        # 정렬 및 페이지네이션
        query = (
            query.order_by(Content.created_at.desc()).offset(skip).limit(limit)
        )

        result = await self.session.execute(query)
        return cast(Sequence[Content], result.scalars().all())

    async def count(
        self,
        user_id: int,
        filters: Optional[ContentFilters] = None,
    ) -> int:
        """콘텐츠 수 조회

        Args:
            user_id: 사용자 ID
            filters: 필터 옵션

        Returns:
            콘텐츠 수
        """
        query = select(func.count(Content.id)).where(
            and_(
                Content.user_id == user_id,
                Content.deleted_at.is_(None),
            )
        )

        # 필터 적용 (get_list와 동일)
        if filters:
            if filters.content_type:
                query = query.where(
                    Content.content_type == filters.content_type
                )

            if filters.category:
                query = query.where(Content.category == filters.category)

            if filters.tags:
                query = query.where(Content.tags.overlap(filters.tags))

            if filters.processing_status:
                query = query.where(
                    Content.processing_status == filters.processing_status
                )

            if filters.date_from:
                query = query.where(Content.created_at >= filters.date_from)

            if filters.date_to:
                query = query.where(Content.created_at <= filters.date_to)

        result = await self.session.execute(query)
        count = result.scalar_one()
        return int(count)

    async def create(self, content: Content) -> Content:
        """콘텐츠 생성

        Args:
            content: 생성할 콘텐츠 객체

        Returns:
            생성된 콘텐츠 객체
        """
        self.session.add(content)
        await self.session.flush()
        await self.session.refresh(content)
        return content

    async def update(self, content: Content) -> Content:
        """콘텐츠 수정

        Args:
            content: 수정할 콘텐츠 객체

        Returns:
            수정된 콘텐츠 객체
        """
        await self.session.flush()
        await self.session.refresh(content)
        return content

    async def soft_delete_batch(
        self, content_ids: list[int], user_id: int
    ) -> int:
        """콘텐츠 벌크 Soft Delete (소유권 확인 포함)

        Args:
            content_ids: 삭제할 콘텐츠 ID 목록
            user_id: 사용자 ID (소유권 확인)

        Returns:
            삭제된 레코드 수
        """
        stmt = (
            update(Content)
            .where(
                and_(
                    Content.id.in_(content_ids),
                    Content.user_id == user_id,
                    Content.deleted_at.is_(None),
                )
            )
            .values(deleted_at=now_utc())
        )

        result = await self.session.execute(stmt)
        await self.session.flush()
        return int(result.rowcount)
