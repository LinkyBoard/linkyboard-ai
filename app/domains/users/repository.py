"""Users 도메인 리포지토리

Spring Boot 사용자 동기화를 위한 데이터 접근 계층입니다.
"""

from datetime import datetime
from typing import Optional, Sequence, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.users.models import User


class UserRepository:
    """사용자 리포지토리"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
        self, user_id: int, include_deleted: bool = False
    ) -> Optional[User]:
        """ID로 사용자 조회

        Args:
            user_id: 사용자 ID
            include_deleted: 삭제된 사용자 포함 여부 (기본: False)

        Returns:
            사용자 객체 또는 None
        """
        query = select(User).where(User.id == user_id)

        if not include_deleted:
            query = query.where(User.deleted_at.is_(None))

        result = await self.session.execute(query)
        return cast(Optional[User], result.scalar_one_or_none())

    async def get_list(
        self,
        skip: int = 0,
        limit: int = 20,
        include_deleted: bool = False,
    ) -> Sequence[User]:
        """사용자 목록 조회

        Args:
            skip: 건너뛸 레코드 수
            limit: 조회할 최대 레코드 수
            include_deleted: 삭제된 사용자 포함 여부 (기본: False)

        Returns:
            사용자 목록
        """
        query = select(User)

        if not include_deleted:
            query = query.where(User.deleted_at.is_(None))

        query = (
            query.offset(skip).limit(limit).order_by(User.created_at.desc())
        )

        result = await self.session.execute(query)
        return cast(Sequence[User], result.scalars().all())

    async def count(self, include_deleted: bool = False) -> int:
        """사용자 수 조회

        Args:
            include_deleted: 삭제된 사용자 포함 여부 (기본: False)

        Returns:
            사용자 수
        """
        query = select(func.count(User.id))

        if not include_deleted:
            query = query.where(User.deleted_at.is_(None))

        result = await self.session.execute(query)
        count = result.scalar_one()
        return int(count)

    async def create(self, user: User) -> User:
        """사용자 생성

        Args:
            user: 생성할 사용자 객체

        Returns:
            생성된 사용자 객체
        """
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update(self, user: User) -> User:
        """사용자 수정

        Args:
            user: 수정할 사용자 객체

        Returns:
            수정된 사용자 객체
        """
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def soft_delete(self, user: User) -> User:
        """사용자 Soft Delete

        Args:
            user: 삭제할 사용자 객체

        Returns:
            삭제된 사용자 객체
        """
        user.deleted_at = datetime.now()
        await self.session.flush()
        await self.session.refresh(user)
        return user
