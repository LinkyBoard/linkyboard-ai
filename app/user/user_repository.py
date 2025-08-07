from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.sql import func

from app.core.models import User
from app.core.repository.base import BaseRepository



class UserRepository(BaseRepository[User]):
    """User 전용 Repository - 사용자 관련 특화 기능 제공"""
    
    def __init__(self):
        super().__init__(User)
    
    async def get_or_create(self, session: AsyncSession, user_id: int) -> User:
        """사용자 조회 또는 생성"""
        # 기존 사용자 조회
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # 새 사용자 생성
            user = User(
                id=user_id,
                is_active=True,
                last_sync_at=func.now()
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        
        return user
    
    async def activate_user(self, session: AsyncSession, user_id: int) -> Optional[User]:
        """사용자 활성화"""
        user = await self.get_by_id(session, user_id)
        if user:
            user.is_active = True
            user.last_sync_at = func.now()
            await session.commit()
            await session.refresh(user)
        return user
    
    async def deactivate_user(self, session: AsyncSession, user_id: int) -> Optional[User]:
        """사용자 비활성화"""
        user = await self.get_by_id(session, user_id)
        if user:
            user.is_active = False
            user.last_sync_at = func.now()
            await session.commit()
            await session.refresh(user)
        return user
    
    async def get_active_users(self, session: AsyncSession, skip: int = 0, limit: int = 100):
        """활성 사용자 목록 조회"""
        return await self.get_all(session, skip=skip, limit=limit, is_active=True)
    
    async def update_sync_time(self, session: AsyncSession, user_id: int) -> Optional[User]:
        """마지막 동기화 시간 업데이트"""
        user = await self.get_by_id(session, user_id)
        if user:
            user.last_sync_at = func.now()
            await session.commit()
            await session.refresh(user)
        return user
    
    async def update_ai_preferences(
        self, 
        session: AsyncSession, 
        user_id: int, 
        preferences: str
    ) -> Optional[User]:
        """AI 개인화 설정 업데이트"""
        user = await self.get_by_id(session, user_id)
        if user:
            user.ai_preferences = preferences
            await session.commit()
            await session.refresh(user)
        return user
    
    async def update_embedding_model_version(
        self, 
        session: AsyncSession, 
        user_id: int, 
        version: str
    ) -> Optional[User]:
        """임베딩 모델 버전 업데이트"""
        user = await self.get_by_id(session, user_id)
        if user:
            user.embedding_model_version = version
            await session.commit()
            await session.refresh(user)
        return user


# 인스턴스 생성
user_repository = UserRepository()