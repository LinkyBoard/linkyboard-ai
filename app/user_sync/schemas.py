"""
User Sync Schemas - Spring Boot 사용자 동기화 스키마
"""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class UserSyncRequest(BaseModel):
    """사용자 동기화 요청 스키마"""
    user_id: int = Field(..., description="Spring Boot 사용자 ID")
    is_active: bool = Field(default=True, description="활성 상태")
    
    # AI 관련 설정은 AI 서버에서 자동 관리하므로 제거
    # ai_preferences: AI 서버에서 사용자 행동 기반 자동 학습
    # embedding_model_version: AI 서버에서 최적 모델 자동 선택


class UserSyncResponse(BaseModel):
    """사용자 동기화 응답 스키마"""
    success: bool = Field(..., description="동기화 성공 여부")
    message: str = Field(..., description="처리 결과 메시지")
    user_id: int = Field(..., description="동기화된 사용자 ID")
    created: bool = Field(..., description="새로 생성되었는지 여부")
    last_sync_at: datetime = Field(..., description="마지막 동기화 시간")


class UserStatusRequest(BaseModel):
    """사용자 상태 변경 요청 스키마"""
    user_id: int = Field(..., description="Spring Boot 사용자 ID")
    is_active: bool = Field(..., description="활성 상태")


class UserStatusResponse(BaseModel):
    """사용자 상태 변경 응답 스키마"""
    success: bool = Field(..., description="상태 변경 성공 여부")
    message: str = Field(..., description="처리 결과 메시지")
    user_id: int = Field(..., description="사용자 ID")
    is_active: bool = Field(..., description="변경된 활성 상태")