"""Users 도메인 라우터

Spring Boot 사용자 동기화 API 엔드포인트입니다.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import verify_internal_api_key
from app.core.schemas import (
    APIResponse,
    ListAPIResponse,
    create_list_response,
    create_response,
)
from app.core.utils.pagination import PageParams
from app.domains.users.schemas import (
    BulkSyncResponse,
    UserBulkSync,
    UserResponse,
    UserSync,
)
from app.domains.users.service import UserService

router = APIRouter()


def get_user_service(session: AsyncSession = Depends(get_db)) -> UserService:
    """UserService 의존성"""
    return UserService(session)


@router.get(
    "",
    response_model=ListAPIResponse[UserResponse],
    dependencies=[Depends(verify_internal_api_key)],
)
async def get_users(
    page_params: PageParams = Depends(),
    include_deleted: bool = False,
    service: UserService = Depends(get_user_service),
):
    """사용자 목록 조회"""
    users, total = await service.get_users(
        page=page_params.page,
        size=page_params.size,
        include_deleted=include_deleted,
    )
    return create_list_response(
        data=[UserResponse.model_validate(user) for user in users],
        total=total,
        page=page_params.page,
        size=page_params.size,
        message="사용자 목록을 조회했습니다.",
    )


@router.get(
    "/{user_id}",
    response_model=APIResponse[UserResponse],
    dependencies=[Depends(verify_internal_api_key)],
)
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


@router.post(
    "",
    response_model=APIResponse[UserResponse],
    status_code=201,
    dependencies=[Depends(verify_internal_api_key)],
)
async def upsert_user(
    user_data: UserSync,
    service: UserService = Depends(get_user_service),
):
    """사용자 동기화 (Upsert)"""
    user = await service.upsert_user(user_data)
    return create_response(
        data=UserResponse.model_validate(user),
        message="사용자가 동기화되었습니다.",
    )


@router.post(
    "/bulk",
    response_model=APIResponse[BulkSyncResponse],
    status_code=201,
    dependencies=[Depends(verify_internal_api_key)],
)
async def bulk_sync_users(
    bulk_data: UserBulkSync,
    service: UserService = Depends(get_user_service),
):
    """벌크 사용자 동기화"""
    result = await service.bulk_upsert_users(bulk_data.users)
    return create_response(
        data=result,
        message="벌크 사용자 동기화가 완료되었습니다.",
    )


@router.delete(
    "/{user_id}",
    status_code=204,
    dependencies=[Depends(verify_internal_api_key)],
)
async def delete_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
):
    """사용자 삭제 (Soft Delete)"""
    await service.delete_user(user_id)
    return None
