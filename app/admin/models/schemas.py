"""
모델 관리 API 스키마
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ModelCatalogBase(BaseModel):
    """모델 카탈로그 기본 스키마"""
    model_name: str = Field(..., description="모델명")
    alias: str = Field(..., description="모델 별칭 (사용자 친화적 이름)")
    provider: str = Field(default="openai", description="모델 제공자")
    model_type: str = Field(..., description="모델 유형 (llm, embedding)")
    role_mask: int = Field(default=7, description="모델 역할 마스크")
    status: str = Field(default="active", description="모델 상태")
    version: Optional[str] = Field(None, description="모델 버전")


class ModelCatalogCreateRequest(ModelCatalogBase):
    """모델 카탈로그 생성 요청"""
    price_input: Optional[float] = Field(None, description="입력 토큰 가격 (USD/1M)")
    price_output: Optional[float] = Field(None, description="출력 토큰 가격 (USD/1M)")
    price_embedding: Optional[float] = Field(None, description="임베딩 가격 (USD/1M)")


class ModelCatalogUpdateRequest(BaseModel):
    """모델 카탈로그 업데이트 요청"""
    alias: Optional[str] = Field(None, description="모델 별칭")
    provider: Optional[str] = Field(None, description="모델 제공자")
    model_type: Optional[str] = Field(None, description="모델 유형")
    role_mask: Optional[int] = Field(None, description="모델 역할 마스크")
    status: Optional[str] = Field(None, description="모델 상태")
    version: Optional[str] = Field(None, description="모델 버전")
    price_input: Optional[float] = Field(None, description="입력 토큰 가격 (USD/1M)")
    price_output: Optional[float] = Field(None, description="출력 토큰 가격 (USD/1M)")
    price_embedding: Optional[float] = Field(None, description="임베딩 가격 (USD/1M)")


class ModelCatalogResponse(ModelCatalogBase):
    """모델 카탈로그 응답"""
    id: int = Field(..., description="모델 ID")
    price_input: Optional[float] = Field(None, description="입력 토큰 가격 (USD/1M)")
    price_output: Optional[float] = Field(None, description="출력 토큰 가격 (USD/1M)")
    price_embedding: Optional[float] = Field(None, description="임베딩 가격 (USD/1M)")
    weight_input: Optional[float] = Field(None, description="입력 토큰 WTU 가중치")
    weight_output: Optional[float] = Field(None, description="출력 토큰 WTU 가중치")
    weight_embedding: Optional[float] = Field(None, description="임베딩 토큰 WTU 가중치")
    is_active: bool = Field(..., description="활성 상태")
    created_at: datetime = Field(..., description="생성일시")
    updated_at: Optional[datetime] = Field(None, description="수정일시")

    class Config:
        from_attributes = True


class ModelListResponse(BaseModel):
    """모델 목록 응답"""
    models: List[ModelCatalogResponse] = Field(..., description="모델 목록")
    total: int = Field(..., description="총 모델 수")


class ModelSelectionResponse(BaseModel):
    """모델 선택을 위한 간단한 응답"""
    id: int = Field(..., description="모델 ID")
    alias: str = Field(..., description="모델 별칭")
    model_type: str = Field(..., description="모델 유형")
    estimated_wtu_per_1k: dict = Field(..., description="1K 토큰당 예상 WTU")
    
    class Config:
        from_attributes = True
