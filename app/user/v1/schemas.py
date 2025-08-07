from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


# Request 스키마
class UserSyncRequest(BaseModel):
    """사용자 동기화 요청 스키마"""
    user_id: int = Field(..., description="Spring Boot 사용자 ID")
    is_active: bool = Field(default=True, description="활성 상태")


# Response 스키마
class UserSyncResponse(BaseModel):
    """사용자 동기화 응답 스키마"""
    success: bool
    message: str
    user_id: int
    created: bool = Field(description="새로 생성되었는지 여부")


class UserResponse(BaseModel):
    """사용자 정보 응답 스키마"""
    id: int
    is_active: bool
    ai_preferences: Optional[str]
    embedding_model_version: Optional[str]
    last_sync_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True