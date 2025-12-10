"""검색 도메인 타입 정의"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SearchFilters:
    """검색 필터

    Attributes:
        content_type: 콘텐츠 타입 리스트 (예: ['webpage', 'youtube'])
        category: 카테고리 (단일)
        tags: 태그 리스트 (OR 조건)
        date_from: 시작 날짜 (created_at >=)
        date_to: 종료 날짜 (created_at <=)

    Example::

        filters = SearchFilters(
            content_type=['webpage'],
            tags=['Python', 'FastAPI'],
            date_from=datetime(2025, 1, 1)
        )
    """

    content_type: Optional[list[str]] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
