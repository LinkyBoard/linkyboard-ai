"""Users 도메인 라우터

Note:
    이 모듈은 템플릿 예제입니다.
    실제 프로젝트에서는 도메인에 맞게 수정하세요.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.schemas import (
    APIResponse,
    ListAPIResponse,
    create_list_response,
    create_response,
)
from app.core.utils.pagination import PageParams
from app.domains.users.schemas import UserCreate, UserResponse, UserUpdate
from app.domains.users.service import UserService

router = APIRouter()


def get_user_service(session: AsyncSession = Depends(get_db)) -> UserService:
    """UserService 의존성"""
    return UserService(session)


@router.get("", response_model=ListAPIResponse[UserResponse])
async def get_users(
    page_params: PageParams = Depends(),
    is_active: Optional[bool] = None,
    service: UserService = Depends(get_user_service),
):
    """사용자 목록 조회"""
    users, total = await service.get_users(
        page=page_params.page,
        size=page_params.size,
        is_active=is_active,
    )
    return create_list_response(
        data=[UserResponse.model_validate(user) for user in users],
        total=total,
        page=page_params.page,
        size=page_params.size,
        message="사용자 목록을 조회했습니다.",
    )


@router.get("/{user_id}", response_model=APIResponse[UserResponse])
async def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
):
    """사용자 상세 조회"""
    user = await service.get_user(user_id)
    return create_response(
        data=UserResponse.model_validate(user),
        message="사용자 정보를 조회했습니다.",
    )


@router.post("", response_model=APIResponse[UserResponse], status_code=201)
async def create_user(
    user_data: UserCreate,
    service: UserService = Depends(get_user_service),
):
    """사용자 생성"""
    user = await service.create_user(user_data)
    return create_response(
        data=UserResponse.model_validate(user),
        message="사용자가 생성되었습니다.",
    )


@router.patch("/{user_id}", response_model=APIResponse[UserResponse])
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    service: UserService = Depends(get_user_service),
):
    """사용자 수정"""
    user = await service.update_user(user_id, user_data)
    return create_response(
        data=UserResponse.model_validate(user),
        message="사용자 정보가 수정되었습니다.",
    )


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
):
    """사용자 삭제"""
    await service.delete_user(user_id)
    return None
