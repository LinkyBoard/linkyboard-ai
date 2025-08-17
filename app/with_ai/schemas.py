"""
With AI Schemas - 모델 선택 지원 AI 질의 스키마
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """AI 질의 요청 스키마"""
    query: str = Field(..., description="질의 내용")
    board_id: UUID = Field(..., description="보드 ID")
    user_id: int = Field(..., description="사용자 ID")
    k: int = Field(default=4, description="검색 결과 수")
    max_out_tokens: int = Field(default=800, description="최대 출력 토큰 수")
    model: Optional[str] = Field(None, description="사용할 AI 모델 (별칭)")
    budget_wtu: Optional[int] = Field(None, description="예산 WTU 제한")
    confidence_target: Optional[float] = Field(None, description="품질 목표 (0.0-1.0)")


class AskResponse(BaseModel):
    """AI 질의 응답 스키마"""
    answer_md: str = Field(..., description="마크다운 형식의 답변")
    claims: List[Dict[str, Any]] = Field(default=[], description="참조된 클레임/문서들")
    usage: Dict[str, Any] = Field(..., description="사용량 정보")
    routing: Dict[str, Any] = Field(..., description="모델 라우팅 정보")


class DraftRequest(BaseModel):
    """초안 작성 요청 스키마"""
    outline: List[str] = Field(..., description="초안 개요")
    board_id: UUID = Field(..., description="보드 ID")
    user_id: int = Field(..., description="사용자 ID")
    max_out_tokens: int = Field(default=1500, description="최대 출력 토큰 수")
    model: Optional[str] = Field(None, description="사용할 AI 모델 (별칭)")
    budget_wtu: Optional[int] = Field(None, description="예산 WTU 제한")
    confidence_target: Optional[float] = Field(None, description="품질 목표 (0.0-1.0)")


class DraftResponse(BaseModel):
    """초안 작성 응답 스키마"""
    draft_md: str = Field(..., description="마크다운 형식의 초안")
    outline_used: List[str] = Field(..., description="사용된 개요")
    usage: Dict[str, Any] = Field(..., description="사용량 정보")
    routing: Dict[str, Any] = Field(..., description="모델 라우팅 정보")


class ModelBudgetRequest(BaseModel):
    """모델별 예산 계산 요청 스키마"""
    input_text: str = Field(..., description="입력 텍스트")
    estimated_output_tokens: int = Field(..., description="예상 출력 토큰 수")
    board_id: UUID = Field(..., description="보드 ID")
    user_id: int = Field(..., description="사용자 ID")


class ModelEstimate(BaseModel):
    """모델별 비용 추정 스키마"""
    model_alias: str = Field(..., description="모델 별칭")
    model_name: str = Field(..., description="실제 모델명")
    input_tokens: int = Field(..., description="입력 토큰 수")
    estimated_output_tokens: int = Field(..., description="예상 출력 토큰 수")
    estimated_wtu: int = Field(..., description="예상 WTU 비용")
    provider: str = Field(..., description="모델 제공자")


class ModelBudgetResponse(BaseModel):
    """모델별 예산 계산 응답 스키마"""
    estimates: List[ModelEstimate] = Field(..., description="모델별 비용 추정")
    total_available_models: int = Field(..., description="사용 가능한 모델 수")


class AvailableModel(BaseModel):
    """사용 가능한 모델 정보 스키마"""
    alias: str = Field(..., description="모델 별칭")
    model_name: str = Field(..., description="실제 모델명")
    provider: str = Field(..., description="모델 제공자")
    description: str = Field(..., description="모델 설명")
    is_default: bool = Field(..., description="기본 모델 여부")


class AvailableModelsResponse(BaseModel):
    """사용 가능한 모델 목록 응답 스키마"""
    models: List[AvailableModel] = Field(..., description="사용 가능한 모델 목록")
    total_count: int = Field(..., description="총 모델 수")
