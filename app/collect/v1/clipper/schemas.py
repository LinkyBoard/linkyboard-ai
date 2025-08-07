from typing import Optional
from pydantic import BaseModel


# Request 스키마
class SaveOnlyRequest(BaseModel):
    """저장만 하기 요청 스키마"""
    thumbnail: str
    title: str
    url: str
    html_content: str


class SummarizeRequest(BaseModel):
    """요약 생성 요청 스키마"""
    url: str
    html_content: str


class SaveWithSummaryRequest(BaseModel):
    """요약과 함께 저장하기 요청 스키마"""
    thumbnail: str
    title: str
    url: str
    memo: Optional[str] = None
    summary: str
    keywords: list[str]
    category: str


# Response 스키마
class SaveOnlyResponse(BaseModel):
    """저장만 하기 응답 스키마"""
    success: bool
    message: str


class SummarizeResponse(BaseModel):
    """요약 생성 응답 스키마"""
    summary: str
    keywords: list[str]
    category: str


class SaveWithSummaryResponse(BaseModel):
    """요약과 함께 저장하기 응답 스키마"""
    success: bool
    message: str
