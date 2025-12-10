"""AI 도메인 스키마 정의
"""

from pydantic import BaseModel, Field


class WebpageSummarizeRequest(BaseModel):
    """웹페이지 요약 요청"""

    url: str = Field(..., description="웹페이지 URL")
    user_id: int = Field(..., description="사용자 ID")
    tag_count: int = Field(5, ge=1, le=20, description="추천 태그 수")
    refresh: bool = Field(False, description="캐시 무시하고 재생성")


class YoutubeSummarizeRequest(BaseModel):
    """YouTube 요약 요청"""

    url: str = Field(..., description="YouTube URL")
    user_id: int
    tag_count: int = Field(5, ge=1, le=20)
    refresh: bool = Field(False)


class PDFSummarizeRequest(BaseModel):
    """PDF 요약 요청"""

    user_id: int
    tag_count: int = Field(5, ge=1, le=20)
    refresh: bool = Field(False)


class SummarizeResponse(BaseModel):
    """요약 응답"""

    content_hash: str
    extracted_text: str
    summary: str
    tags: list[str]
    category: str
    candidate_tags: list[str]
    candidate_categories: list[str]
    cached: bool
