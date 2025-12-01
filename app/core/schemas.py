"""공통 API 응답 스키마

이 모듈은 API 응답의 일관된 구조를 정의합니다.

Usage::

    # 단일 데이터 응답
    from app.core.schemas import APIResponse, create_response
    return create_response(data=user, message="사용자 조회 성공")

    # 목록 데이터 응답 (페이지네이션)
    from app.core.schemas import ListAPIResponse, create_list_response
    return create_list_response(data=users, total=100, page=1, size=20)

Note:
    Generic 타입의 classmethod는 Pydantic에서 제한이 있으므로,
    팩토리 함수(create_response, create_list_response)를 사용하거나
    직접 생성자를 호출하세요.
"""

import math
from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class BaseSchema(BaseModel):
    """기본 스키마 (ORM 모델 변환용)"""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class TimestampMixin(BaseModel):
    """타임스탬프 믹스인"""

    created_at: datetime
    updated_at: Optional[datetime] = None


class APIResponse(BaseModel, Generic[DataT]):
    """단일 데이터 API 응답

    Example::

        @router.get("/{id}", response_model=APIResponse[UserResponse])
        async def get_user(id: int):
            user = await service.get_user(id)
            return APIResponse(
                success=True,
                data=UserResponse.model_validate(user),
                message="사용자 조회 성공",
            )
    """

    success: bool = True
    message: str = "요청이 성공적으로 처리되었습니다."
    data: Optional[DataT] = None


class PageMeta(BaseModel):
    """페이지네이션 메타 정보"""

    total: int = Field(..., description="전체 아이템 수")
    page: int = Field(..., description="현재 페이지")
    size: int = Field(..., description="페이지 크기")
    total_pages: int = Field(..., description="전체 페이지 수")
    has_next: bool = Field(..., description="다음 페이지 존재 여부")
    has_prev: bool = Field(..., description="이전 페이지 존재 여부")


class ListAPIResponse(BaseModel, Generic[DataT]):
    """목록 데이터 API 응답 (페이지네이션 포함)

    Example::

        @router.get("", response_model=ListAPIResponse[UserResponse])
        async def get_users(page_params: PageParams = Depends()):
            users, total = await service.get_users(page_params)
            return create_list_response(
                data=[UserResponse.model_validate(u) for u in users],
                total=total,
                page=page_params.page,
                size=page_params.size,
            )
    """

    success: bool = True
    message: str = "요청이 성공적으로 처리되었습니다."
    data: list[DataT] = Field(default_factory=list)
    meta: PageMeta


def create_response(
    data: Optional[DataT] = None,
    message: str = "요청이 성공적으로 처리되었습니다.",
    success: bool = True,
) -> APIResponse[DataT]:
    """API 응답 생성 팩토리 함수

    Args:
        data: 응답 데이터
        message: 응답 메시지
        success: 성공 여부

    Returns:
        APIResponse 인스턴스
    """
    return APIResponse(success=success, message=message, data=data)


def create_list_response(
    data: list[DataT],
    total: int,
    page: int,
    size: int,
    message: str = "요청이 성공적으로 처리되었습니다.",
) -> ListAPIResponse[DataT]:
    """목록 API 응답 생성 팩토리 함수

    Args:
        data: 목록 데이터
        total: 전체 아이템 수
        page: 현재 페이지
        size: 페이지 크기
        message: 응답 메시지

    Returns:
        ListAPIResponse 인스턴스
    """
    total_pages = math.ceil(total / size) if size > 0 else 0
    return ListAPIResponse(
        success=True,
        message=message,
        data=data,
        meta=PageMeta(
            total=total,
            page=page,
            size=size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        ),
    )


class ErrorDetail(BaseModel):
    """에러 상세 정보"""

    code: str = Field(..., description="에러 코드")
    message: str = Field(..., description="에러 메시지")
    detail: Optional[dict[str, Any]] = Field(default=None, description="추가 정보")


class ErrorResponse(BaseModel):
    """에러 API 응답

    Example::

        {
            "success": false,
            "message": "사용자를 찾을 수 없습니다.",
            "error": {
                "code": "USER_NOT_FOUND",
                "message": "사용자를 찾을 수 없습니다.",
                "detail": {"user_id": 123}
            }
        }
    """

    success: bool = False
    message: str
    error: ErrorDetail
