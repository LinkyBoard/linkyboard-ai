"""
YouTube 요약 API 스키마
"""

from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class YouTubeSummarizeRequest(BaseModel):
    """유튜브 요약 생성 요청 스키마"""
    url: str = Field(..., description="YouTube 동영상 URL")
    title: str = Field(..., description="동영상 제목")
    transcript: str = Field(..., description="YouTube 스크립트/자막 내용")
    user_id: int = Field(..., description="사용자 ID")


class YouTubeSummarizeResponse(BaseModel):
    """유튜브 요약 생성 응답 스키마"""
    summary: str = Field(..., description="동영상 요약")
    tags: List[str] = Field(..., description="추천 태그 목록")
    category: str = Field(..., description="추천 카테고리")
    usage: Optional[Dict] = Field(None, description="사용량 정보")