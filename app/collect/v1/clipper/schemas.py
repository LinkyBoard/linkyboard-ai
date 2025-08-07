from typing import Optional
from pydantic import BaseModel


# Request 스키마
class WebpageSaveRequest(BaseModel):
    """웹페이지 저장 요청 스키마"""
    user_id: int
    thumbnail: str
    title: str
    url: str
    summary: Optional[str] = None
    keywords: Optional[list[str]] = None
    category: str
    memo: Optional[str] = None
    html_content: Optional[str] = None
    html_content: str


class SummarizeRequest(BaseModel):
    """요약 생성 요청 스키마"""
    url: str
    html_content: str


# Response 스키마
class WebpageSaveResponse(BaseModel):
    """저장만 하기 응답 스키마"""
    success: bool
    message: str


class SummarizeResponse(BaseModel):
    """요약 생성 응답 스키마"""
    summary: str
    keywords: list[str]
    category: str
