"""
Board AI Schemas - 선택된 아이템 기반 AI 작업 스키마
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SelectedItem(BaseModel):
    """선택된 아이템 정보"""
    item_id: int = Field(..., description="아이템 ID")
    include_summary: bool = Field(default=True, description="요약 포함 여부")
    include_content: bool = Field(default=False, description="전체 내용 포함 여부")


class AskWithItemsRequest(BaseModel):
    """선택된 아이템 기반 AI 질의 요청 스키마"""
    query: str = Field(..., description="질의 내용")
    instruction: str = Field(..., description="AI에게 주는 작업 지시사항") 
    selected_items: List[SelectedItem] = Field(..., description="선택된 아이템 목록")
    board_id: int = Field(..., description="보드 ID")
    user_id: int = Field(..., description="사용자 ID")
    model_alias: str = Field(..., description="사용할 AI 모델 별칭")
    max_output_tokens: int = Field(default=1500, description="최대 출력 토큰 수")


class AskWithItemsResponse(BaseModel):
    """선택된 아이템 기반 AI 질의 응답 스키마"""
    answer_md: str = Field(..., description="마크다운 형식의 답변")
    used_items: List[Dict[str, Any]] = Field(..., description="사용된 아이템 정보")
    usage: Dict[str, Any] = Field(..., description="사용량 정보")
    model_info: Dict[str, Any] = Field(..., description="사용된 모델 정보")


class DraftWithItemsRequest(BaseModel):
    """선택된 아이템 기반 초안 작성 요청 스키마"""
    requirements: str = Field(..., description="작성 요구사항 및 스타일 지시")
    selected_items: List[int] = Field(..., description="선택된 아이템 ID 목록")
    board_id: int = Field(..., description="보드 ID")
    user_id: int = Field(..., description="사용자 ID")
    model_alias: str = Field(..., description="사용할 AI 모델 별칭")


class DraftWithItemsResponse(BaseModel):
    """선택된 아이템 기반 초안 작성 응답 스키마"""
    title: str = Field(..., description="생성된 초안 제목")
    draft_md: str = Field(..., description="마크다운 형식의 초안")
    used_items: List[Dict[str, Any]] = Field(..., description="사용된 아이템 정보")
    usage: Dict[str, Any] = Field(..., description="사용량 정보")
    model_info: Dict[str, Any] = Field(..., description="사용된 모델 정보")


class CostEstimateRequest(BaseModel):
    """비용 추정 요청 스키마"""
    selected_items: List[int] = Field(..., description="선택된 아이템 ID 목록")
    task_description: str = Field(..., description="수행할 작업 설명")
    board_id: int = Field(..., description="보드 ID")
    user_id: int = Field(..., description="사용자 ID")
    estimated_output_tokens: int = Field(default=1500, description="예상 출력 토큰 수")


class ModelCostEstimate(BaseModel):
    """모델별 비용 추정 정보"""
    model_alias: str = Field(..., description="모델 별칭")
    model_name: str = Field(..., description="실제 모델명")
    provider: str = Field(..., description="모델 제공자")
    estimated_input_tokens: int = Field(..., description="예상 입력 토큰 수")
    estimated_output_tokens: int = Field(..., description="예상 출력 토큰 수")
    estimated_wtu_cost: int = Field(..., description="예상 WTU 비용")
    is_recommended: bool = Field(default=False, description="추천 모델 여부")


class CostEstimateResponse(BaseModel):
    """비용 추정 응답 스키마"""
    estimates: List[ModelCostEstimate] = Field(..., description="모델별 비용 추정")
    total_selected_items: int = Field(..., description="선택된 아이템 수")
    total_content_length: int = Field(..., description="전체 콘텐츠 길이")


class AvailableModel(BaseModel):
    """사용 가능한 모델 정보"""
    alias: str = Field(..., description="모델 별칭")
    model_name: str = Field(..., description="실제 모델명")
    provider: str = Field(..., description="모델 제공자")
    description: Optional[str] = Field(None, description="모델 설명")
    input_cost_per_1k: float = Field(..., description="1K 토큰당 입력 비용 (WTU)")
    output_cost_per_1k: float = Field(..., description="1K 토큰당 출력 비용 (WTU)")
    is_default: bool = Field(default=False, description="기본 추천 모델 여부")


class AvailableModelsResponse(BaseModel):
    """사용 가능한 모델 목록 응답"""
    models: List[AvailableModel] = Field(..., description="사용 가능한 모델 목록")
    total_count: int = Field(..., description="총 모델 수")
    default_model: Optional[str] = Field(None, description="기본 추천 모델 별칭")
