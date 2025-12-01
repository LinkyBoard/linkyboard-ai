"""Users 도메인 리포지토리"""

from typing import Optional, Sequence, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.users.models import User


class UserRepository:
    """사용자 리포지토리"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """ID로 사용자 조회"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return cast(Optional[User], result.scalar_one_or_none())

    async def get_by_username(self, username: str) -> Optional[User]:
        """사용자명으로 사용자 조회"""
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return cast(Optional[User], result.scalar_one_or_none())

    async def get_list(
        self,
        skip: int = 0,
        limit: int = 20,
        is_active: Optional[bool] = None,
    ) -> Sequence[User]:
        """사용자 목록 조회"""
        query = select(User)

        if is_active is not None:
            query = query.where(User.is_active == is_active)

        query = (
            query.offset(skip).limit(limit).order_by(User.created_at.desc())
        )
        result = await self.session.execute(query)
        return cast(Sequence[User], result.scalars().all())

    async def count(self, is_active: Optional[bool] = None) -> int:
        """사용자 수 조회"""
        query = select(func.count(User.id))

        if is_active is not None:
            query = query.where(User.is_active == is_active)

        result = await self.session.execute(query)
        count = result.scalar_one()
        return int(count)

    async def create(self, user: User) -> User:
        """사용자 생성"""
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update(self, user: User) -> User:
        """사용자 수정"""
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        """사용자 삭제"""
        await self.session.delete(user)
        await self.session.flush()

    async def exists_by_username(
        self, username: str, exclude_id: Optional[int] = None
    ) -> bool:
        """사용자명 존재 여부 확인"""
        query = select(User.id).where(User.username == username)
        if exclude_id:
            query = query.where(User.id != exclude_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None
