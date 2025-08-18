"""
Content 관리 API 스키마
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ContentDeleteRequest(BaseModel):
    """콘텐츠 삭제 요청 스키마"""
    item_ids: List[int] = Field(..., description="삭제할 Item ID 목록", min_length=1)
    user_id: int = Field(..., description="사용자 ID")


class ContentDeleteResponse(BaseModel):
    """콘텐츠 삭제 응답 스키마"""
    success: bool = Field(..., description="전체 작업 성공 여부")
    message: str = Field(..., description="응답 메시지")
    deleted_count: int = Field(..., description="실제 삭제된 항목 수")
    failed_items: List[int] = Field(default=[], description="삭제 실패한 Item ID 목록")
    total_requested: int = Field(..., description="요청된 총 항목 수")


class ContentDeleteBatchResponse(BaseModel):
    """콘텐츠 배치 삭제 상세 응답 스키마"""
    success: bool = Field(..., description="전체 작업 성공 여부")
    message: str = Field(..., description="응답 메시지")
    results: List[dict] = Field(..., description="각 항목별 삭제 결과")
    summary: dict = Field(..., description="삭제 결과 요약")