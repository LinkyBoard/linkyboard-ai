"""
보드 모델 정책 API 스키마
"""

from typing import List, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class BoardModelPolicyBase(BaseModel):
    """보드 모델 정책 기본 스키마"""
    default_model_id: Optional[int] = Field(None, description="기본 모델 ID")
    allowed_model_ids: List[int] = Field(default=[], description="허용 모델 ID 목록")
    budget_wtu: Optional[int] = Field(None, description="월 예산 WTU")
    confidence_target: Optional[float] = Field(None, ge=0.0, le=1.0, description="품질 목표 점수")


class BoardModelPolicyCreateRequest(BoardModelPolicyBase):
    """보드 모델 정책 생성 요청"""
    pass


class BoardModelPolicyUpdateRequest(BaseModel):
    """보드 모델 정책 업데이트 요청"""
    default_model_id: Optional[int] = Field(None, description="기본 모델 ID")
    allowed_model_ids: Optional[List[int]] = Field(None, description="허용 모델 ID 목록")
    budget_wtu: Optional[int] = Field(None, description="월 예산 WTU")
    confidence_target: Optional[float] = Field(None, ge=0.0, le=1.0, description="품질 목표 점수")


class BoardModelPolicyResponse(BoardModelPolicyBase):
    """보드 모델 정책 응답"""
    board_id: UUID = Field(..., description="보드 ID")
    created_at: datetime = Field(..., description="생성일시")
    updated_at: Optional[datetime] = Field(None, description="수정일시")

    class Config:
        from_attributes = True


class ModelSelectionInfo(BaseModel):
    """모델 선택 정보"""
    id: int = Field(..., description="모델 ID")
    alias: str = Field(..., description="모델 별칭")
    model_type: str = Field(..., description="모델 유형")
    estimated_wtu_per_1k: dict = Field(..., description="1K 토큰당 예상 WTU")


class AvailableModelsResponse(BaseModel):
    """사용 가능한 모델 목록 응답"""
    board_id: UUID = Field(..., description="보드 ID")
    models: List[ModelSelectionInfo] = Field(..., description="사용 가능한 모델 목록")
    default_model_id: Optional[int] = Field(None, description="기본 모델 ID")
