"""
User Sync Router - Spring Boot 사용자 동기화 엔드포인트
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from .service import get_user_sync_service, UserSyncService
from .schemas import (
    UserSyncRequest,
    UserSyncResponse, 
    UserStatusRequest,
    UserStatusResponse
)

logger = get_logger(__name__)

# Router 인스턴스 생성
router = APIRouter(
    prefix="/user-sync",
    tags=["user-sync"],
    responses={
        400: {"description": "Bad Request"},
        404: {"description": "User not found"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    }
)


@router.post("/sync", response_model=UserSyncResponse)
async def sync_user(
    request: UserSyncRequest,
    session: AsyncSession = Depends(get_db),
    service: UserSyncService = Depends(get_user_sync_service)
):
    """
    Spring Boot에서 사용자 정보 동기화
    
    사용자 가입, 정보 변경 시 Spring Boot에서 호출하는 API입니다.
    기존 사용자가 있으면 업데이트, 없으면 새로 생성합니다.
    """
    try:
        logger.info(f"User sync request received - user_id: {request.user_id}")
        
        result = await service.sync_user(
            session=session,
            request_data=request
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"User sync validation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"User sync failed: {str(e)}")
        raise HTTPException(status_code=500, detail="사용자 동기화 중 오류가 발생했습니다.")


@router.put("/status", response_model=UserStatusResponse)
async def update_user_status(
    request: UserStatusRequest,
    session: AsyncSession = Depends(get_db),
    service: UserSyncService = Depends(get_user_sync_service)
):
    """
    사용자 활성 상태 변경
    
    사용자 탈퇴, 복구 등의 상태 변경 시 Spring Boot에서 호출하는 API입니다.
    """
    try:
        logger.info(f"User status update request - user_id: {request.user_id}, active: {request.is_active}")
        
        result = await service.update_user_status(
            session=session,
            request_data=request
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"User status update validation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"User status update failed: {str(e)}")
        raise HTTPException(status_code=500, detail="사용자 상태 변경 중 오류가 발생했습니다.")


@router.get("/status/{user_id}")
async def get_user_sync_status(
    user_id: int,
    session: AsyncSession = Depends(get_db),
    service: UserSyncService = Depends(get_user_sync_service)
):
    """
    사용자 동기화 상태 조회
    
    특정 사용자의 AI 서비스 동기화 상태를 확인합니다.
    """
    try:
        logger.info(f"User sync status request - user_id: {user_id}")
        
        status = await service.get_user_sync_status(
            session=session,
            user_id=user_id
        )
        
        if not status:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user sync status: {str(e)}")
        raise HTTPException(status_code=500, detail="사용자 상태 조회 중 오류가 발생했습니다.")