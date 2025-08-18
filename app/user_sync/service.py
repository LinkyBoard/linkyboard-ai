"""
User Sync Service - Spring Boot 사용자 동기화 서비스
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func
from datetime import datetime

from app.core.logging import get_logger
from app.user.user_repository import UserRepository
from app.core.models import User
from .schemas import UserSyncRequest, UserSyncResponse, UserStatusRequest, UserStatusResponse

logger = get_logger(__name__)


class UserSyncService:
    """Spring Boot 사용자 동기화 서비스"""
    
    def __init__(self):
        self.user_repository = UserRepository()
        logger.info("User sync service initialized")
    
    async def sync_user(
        self, 
        session: AsyncSession,
        request_data: UserSyncRequest
    ) -> UserSyncResponse:
        """
        Spring Boot에서 사용자 정보를 AI 서비스로 동기화
        
        Args:
            session: 데이터베이스 세션
            request_data: 동기화할 사용자 정보
            
        Returns:
            동기화 결과
        """
        try:
            logger.info(f"Syncing user {request_data.user_id} from Spring Boot")
            
            # 기존 사용자 확인
            existing_user = await self.user_repository.get_by_id(session, request_data.user_id)
            created = False
            current_time = datetime.utcnow()
            
            if existing_user:
                # 기존 사용자 업데이트
                logger.info(f"Updating existing user {request_data.user_id}")
                
                # AI 설정은 기존 값 유지하고 동기화 시간과 활성 상태만 업데이트
                user = await self.user_repository.update(
                    session,
                    entity_id=request_data.user_id,
                    is_active=request_data.is_active,
                    last_sync_at=current_time,
                    updated_at=current_time
                )
            else:
                # 새 사용자 생성
                logger.info(f"Creating new user {request_data.user_id}")
                created = True
                
                # AI 설정은 AI 서버에서 기본값으로 자동 관리
                user = await self.user_repository.create(
                    session,
                    id=request_data.user_id,
                    is_active=request_data.is_active,
                    last_sync_at=current_time
                )
            
            # 변경사항 커밋
            await session.commit()
            
            action = "생성" if created else "업데이트"
            message = f"사용자 {request_data.user_id}가 성공적으로 {action}되었습니다."
            
            logger.info(f"User sync completed: {message}")
            
            return UserSyncResponse(
                success=True,
                message=message,
                user_id=request_data.user_id,
                created=created,
                last_sync_at=current_time
            )
            
        except Exception as e:
            logger.error(f"Failed to sync user {request_data.user_id}: {str(e)}")
            await session.rollback()
            raise Exception(f"사용자 동기화 중 오류가 발생했습니다: {str(e)}")
    
    async def update_user_status(
        self,
        session: AsyncSession,
        request_data: UserStatusRequest
    ) -> UserStatusResponse:
        """
        사용자 활성 상태 업데이트 (탈퇴/복구 등)
        
        Args:
            session: 데이터베이스 세션
            request_data: 상태 변경 정보
            
        Returns:
            상태 변경 결과
        """
        try:
            logger.info(f"Updating user {request_data.user_id} status to active={request_data.is_active}")
            
            # 사용자 확인
            user = await self.user_repository.get_by_id(session, request_data.user_id)
            if not user:
                raise ValueError(f"사용자 {request_data.user_id}를 찾을 수 없습니다.")
            
            # 상태 업데이트
            await self.user_repository.update(
                session,
                entity_id=request_data.user_id,
                is_active=request_data.is_active,
                last_sync_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            await session.commit()
            
            status_text = "활성화" if request_data.is_active else "비활성화"
            message = f"사용자 {request_data.user_id}가 성공적으로 {status_text}되었습니다."
            
            logger.info(f"User status update completed: {message}")
            
            return UserStatusResponse(
                success=True,
                message=message,
                user_id=request_data.user_id,
                is_active=request_data.is_active
            )
            
        except Exception as e:
            logger.error(f"Failed to update user {request_data.user_id} status: {str(e)}")
            await session.rollback()
            raise Exception(f"사용자 상태 변경 중 오류가 발생했습니다: {str(e)}")
    
    async def get_user_sync_status(
        self,
        session: AsyncSession,
        user_id: int
    ) -> Optional[dict]:
        """
        사용자 동기화 상태 조회
        
        Args:
            session: 데이터베이스 세션
            user_id: 조회할 사용자 ID
            
        Returns:
            사용자 동기화 상태 정보
        """
        try:
            user = await self.user_repository.get_by_id(session, user_id)
            if not user:
                return None
            
            return {
                "user_id": user.id,
                "is_active": user.is_active,
                "ai_preferences": user.ai_preferences,
                "embedding_model_version": user.embedding_model_version,
                "last_sync_at": user.last_sync_at,
                "created_at": user.created_at,
                "updated_at": user.updated_at
            }
            
        except Exception as e:
            logger.error(f"Failed to get sync status for user {user_id}: {str(e)}")
            return None


# 전역 서비스 인스턴스
user_sync_service = UserSyncService()


def get_user_sync_service() -> UserSyncService:
    """UserSyncService 인스턴스 반환"""
    return user_sync_service