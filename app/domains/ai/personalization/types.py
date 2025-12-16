"""개인화 관련 타입 정의"""

from typing import TypedDict


class ScoredTag(TypedDict):
    """점수가 매겨진 태그

    Attributes:
        tag: 태그 이름
        final_score: 최종 점수
        base_score: LLM 제안 순서 기반 점수
        personalization_score: 개인화 점수 (유사도 × 빈도)
        recency_score: 최근성 점수
        popularity_score: 전역 인기도 점수
    """

    tag: str
    final_score: float
    base_score: float
    personalization_score: float
    recency_score: float
    popularity_score: float


class ScoredCategory(TypedDict):
    """점수가 매겨진 카테고리

    Attributes:
        category: 카테고리 이름
        final_score: 최종 점수
    """

    category: str
    final_score: float
