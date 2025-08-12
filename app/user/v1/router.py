from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from .schemas import (
    UserSyncRequest,
    UserSyncResponse,
    UserResponse,
)
from .service import user_service

logger = get_logger(__name__)

# Router 인스턴스 생성
router = APIRouter(
    prefix="/api/v1/user",
    tags=["user"],
    responses={
        400: {"description": "Bad Request"},
        404: {"description": "Not found"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)


@router.post("/sync", response_model=UserSyncResponse)
async def sync_user(
    request_data: UserSyncRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    사용자 동기화
    
    Spring Boot 서버에서 사용자 정보를 받아서 AI 서버에 동기화합니다.
    """
    try:
        logger.info(f"Received user sync request for user {request_data.user_id}")
        
        result = await user_service.sync_user(session, request_data)
        logger.info(f"User sync completed successfully for user {request_data.user_id}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to sync user {request_data.user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int = Path(..., description="사용자 ID"),
    session: AsyncSession = Depends(get_db)
):
    """
    사용자 정보 조회
    """
    try:
        logger.info(f"Received get user request for user {user_id}")
        
        result = await user_service.get_user(session, user_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
        logger.info(f"User retrieved successfully for user {user_id}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
