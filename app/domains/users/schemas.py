"""Users 도메인 스키마 정의

Note:
    이 모듈은 템플릿 예제입니다.
    실제 프로젝트에서는 도메인에 맞게 수정하세요.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserBase(BaseModel):
    """사용자 기본 스키마"""

    username: str = Field(
        ..., min_length=3, max_length=100, description="사용자명"
    )
    full_name: Optional[str] = Field(None, max_length=255, description="전체 이름")


class UserCreate(UserBase):
    """사용자 생성 스키마"""

    password: str = Field(
        ..., min_length=8, max_length=100, description="비밀번호"
    )


class UserUpdate(BaseModel):
    """사용자 수정 스키마"""

    username: Optional[str] = Field(
        None, min_length=3, max_length=100, description="사용자명"
    )
    full_name: Optional[str] = Field(None, max_length=255, description="전체 이름")
    password: Optional[str] = Field(
        None, min_length=8, max_length=100, description="비밀번호"
    )
    is_active: Optional[bool] = Field(None, description="활성화 여부")


class UserResponse(UserBase):
    """사용자 응답 스키마"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
