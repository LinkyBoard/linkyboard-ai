"""Users 도메인 스키마 정의

Spring Boot 서버와의 사용자 동기화를 위한 Pydantic 스키마입니다.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserSync(BaseModel):
    """사용자 동기화 요청 스키마

    Spring Boot에서 생성된 사용자 ID를 받아 동기화합니다.
    """

    id: int = Field(..., gt=0, description="Spring Boot 사용자 ID")


class UserBulkSync(BaseModel):
    """벌크 사용자 동기화 요청 스키마"""

    users: list[UserSync] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="동기화할 사용자 목록 (최대 1000명)",
    )


class UserResponse(BaseModel):
    """사용자 응답 스키마"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None


class BulkSyncResponse(BaseModel):
    """벌크 동기화 응답 스키마"""

    total: int = Field(..., description="요청된 총 사용자 수")
    created: int = Field(..., description="새로 생성된 사용자 수")
    updated: int = Field(..., description="업데이트된 사용자 수")
    restored: int = Field(..., description="복구된 사용자 수")
