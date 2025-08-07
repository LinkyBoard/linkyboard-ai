from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func

from app.core.logging import get_logger
from app.user.user_repository import UserRepository
from .schemas import (
    UserSyncRequest,
    UserSyncResponse,
    UserResponse,
)

logger = get_logger("user_service")


class UserService:
    """사용자 비즈니스 로직 서비스"""
    
    def __init__(self):
        self.user_repository = UserRepository()
        logger.info("User service initialized")

    async def sync_user(
        self, 
        session: AsyncSession,
        request_data: UserSyncRequest
    ) -> UserSyncResponse:
        """
        Spring Boot에서 사용자 동기화
        """
        try:
            logger.info(f"Syncing user {request_data.user_id}")
            
            # 기존 사용자 확인
            existing_user = await self.user_repository.get_by_id(session, request_data.user_id)
            created = False
            
            if existing_user:
                logger.info(f"Updating existing user {request_data.user_id}")
                user = await self.user_repository.update(
                    session,
                    request_data.user_id,
                    is_active=request_data.is_active,
                    last_sync_at=func.now(),
                    updated_at=func.now()
                )
            else:
                logger.info(f"Creating new user {request_data.user_id}")
                user = await self.user_repository.create(
                    session,
                    id=request_data.user_id,
                    is_active=request_data.is_active,
                    last_sync_at=func.now()
                )
                created = True

            logger.bind(database=True).info(f"User {request_data.user_id} synchronized successfully")
            return UserSyncResponse(
                success=True,
                message="사용자가 성공적으로 동기화되었습니다.",
                user_id=user.id,
                created=created
            )
        
        except Exception as e:
            logger.error(f"Failed to sync user {request_data.user_id}: {str(e)}")
            raise Exception(f"사용자 동기화 중 오류가 발생했습니다: {str(e)}")
    
    async def get_user(
        self, 
        session: AsyncSession,
        user_id: int
    ) -> Optional[UserResponse]:
        """
        사용자 정보 조회
        """
        try:
            logger.info(f"Getting user {user_id}")
            
            user = await self.user_repository.get_by_id(session, user_id)
            
            if not user:
                logger.warning(f"User {user_id} not found")
                return None
            
            logger.bind(database=True).info(f"User {user_id} retrieved successfully")
            return UserResponse.from_orm(user)
        
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {str(e)}")
            raise Exception(f"사용자 조회 중 오류가 발생했습니다: {str(e)}")


# 서비스 인스턴스 생성 (싱글톤 패턴)
user_service = UserService()