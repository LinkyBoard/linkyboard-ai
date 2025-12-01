"""Users 도메인 서비스"""

import hashlib
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.users.exceptions import (
    UsernameAlreadyExistsException,
    UserNotFoundException,
)
from app.domains.users.models import User
from app.domains.users.repository import UserRepository
from app.domains.users.schemas import UserCreate, UserUpdate


class UserService:
    """사용자 서비스"""

    def __init__(self, session: AsyncSession):
        self.repository = UserRepository(session)

    @staticmethod
    def _hash_password(password: str) -> str:
        """비밀번호 해시 (실제 프로젝트에서는 bcrypt 등 사용 권장)"""
        return hashlib.sha256(password.encode()).hexdigest()

    async def get_user(self, user_id: int) -> User:
        """사용자 조회"""
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundException(user_id=user_id)
        return user

    async def get_user_by_username(self, username: str) -> User:
        """사용자명으로 사용자 조회"""
        user = await self.repository.get_by_username(username)
        if not user:
            raise UserNotFoundException()
        return user

    async def get_users(
        self,
        page: int = 1,
        size: int = 20,
        is_active: Optional[bool] = None,
    ) -> tuple[list[User], int]:
        """사용자 목록 조회"""
        skip = (page - 1) * size
        users = await self.repository.get_list(
            skip=skip, limit=size, is_active=is_active
        )
        total = await self.repository.count(is_active=is_active)
        return list(users), total

    async def create_user(self, user_data: UserCreate) -> User:
        """사용자 생성"""
        # 사용자명 중복 확인
        if await self.repository.exists_by_username(user_data.username):
            raise UsernameAlreadyExistsException(username=user_data.username)

        # 사용자 생성
        user = User(
            username=user_data.username,
            full_name=user_data.full_name,
            hashed_password=self._hash_password(user_data.password),
        )

        return await self.repository.create(user)

    async def update_user(self, user_id: int, user_data: UserUpdate) -> User:
        """사용자 수정"""
        user = await self.get_user(user_id)

        # 사용자명 변경 시 중복 확인
        if user_data.username and user_data.username != user.username:
            if await self.repository.exists_by_username(
                user_data.username, exclude_id=user_id
            ):
                raise UsernameAlreadyExistsException(
                    username=user_data.username
                )
            user.username = user_data.username

        if user_data.full_name is not None:
            user.full_name = user_data.full_name

        if user_data.password:
            user.hashed_password = self._hash_password(user_data.password)

        if user_data.is_active is not None:
            user.is_active = user_data.is_active

        return await self.repository.update(user)

    async def delete_user(self, user_id: int) -> None:
        """사용자 삭제"""
        user = await self.get_user(user_id)
        await self.repository.delete(user)
