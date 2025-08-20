"""
YouTube API 스키마
"""

from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from app.collect.v1.clipper.schemas import DuplicateCandidateResponse


class YouTubeSyncRequest(BaseModel):
    """유튜브 동기화 요청 스키마"""
    item_id: int = Field(..., description="Item ID")
    user_id: int = Field(..., description="사용자 ID")
    thumbnail: str = Field(..., description="썸네일 이미지 (URL)")
    title: str = Field(..., description="동영상 제목")
    url: str = Field(..., description="YouTube 동영상 URL")
    summary: Optional[str] = Field(None, description="동영상 요약")
    tags: Optional[List[str]] = Field(None, description="태그 목록")
    category: str = Field(..., description="카테고리")
    memo: Optional[str] = Field(None, description="사용자 메모")
    transcript: str = Field(..., description="YouTube 스크립트/자막 내용")


class YouTubeSyncResponse(BaseModel):
    """유튜브 동기화 응답 스키마"""
    success: bool = Field(..., description="성공 여부")
    message: str = Field(..., description="응답 메시지")
    duplicate_candidates: Optional[List[DuplicateCandidateResponse]] = Field(None, description="중복 후보")


class YouTubeSummarizeRequest(BaseModel):
    """유튜브 요약 생성 요청 스키마"""
    url: str = Field(..., description="YouTube 동영상 URL")
    user_id: int = Field(..., description="사용자 ID")
    tag_count: int = Field(default=5, description="추천 태그 수")


class YouTubeSummarizeResponse(BaseModel):
    """유튜브 요약 생성 응답 스키마"""
    title: str = Field(..., description="동영상 제목")
    summary: str = Field(..., description="동영상 요약")
    tags: List[str] = Field(..., description="추천 태그 목록")
    category: str = Field(..., description="추천 카테고리")
    thumbnail: Optional[str] = Field(None, description="썸네일 이미지 URL")


