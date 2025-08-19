"""
Board Sync Schemas - 보드 동기화 관련 스키마
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class BoardSyncRequest(BaseModel):
    """보드 동기화 요청 스키마"""
    board_id: int = Field(..., description="보드 ID")
    user_id: int = Field(..., description="사용자 ID")
    title: str = Field(..., description="보드 제목")
    description: Optional[str] = Field(None, description="보드 설명")
    board_type: str = Field(default="collection", description="보드 타입")
    visibility: str = Field(default="private", description="공개 설정")
    is_active: bool = Field(default=True, description="활성 상태")
    created_at: datetime = Field(..., description="생성 시간")
    updated_at: Optional[datetime] = Field(None, description="수정 시간")


class BoardItemSyncRequest(BaseModel):
    """보드 아이템 동기화 요청 스키마"""
    board_id: int = Field(..., description="보드 ID")
    item_ids: List[int] = Field(..., description="아이템 ID 목록")


class BoardDeleteRequest(BaseModel):
    """보드 삭제 요청 스키마"""
    board_id: int = Field(..., description="삭제할 보드 ID")
    user_id: int = Field(..., description="사용자 ID")


class BoardSyncResponse(BaseModel):
    """보드 동기화 응답 스키마"""
    success: bool = Field(..., description="동기화 성공 여부")
    board_id: int = Field(..., description="보드 ID")
    message: str = Field(..., description="응답 메시지")
    synced_at: datetime = Field(..., description="동기화 완료 시간")
    analytics_triggered: bool = Field(default=False, description="분석 트리거 여부")


class BoardItemSyncResponse(BaseModel):
    """보드 아이템 동기화 응답 스키마"""
    success: bool = Field(..., description="동기화 성공 여부")
    board_id: int = Field(..., description="보드 ID")
    synced_items: int = Field(..., description="동기화된 아이템 수")
    removed_items: int = Field(default=0, description="제거된 아이템 수")
    message: str = Field(..., description="응답 메시지")
    synced_at: datetime = Field(..., description="동기화 완료 시간")
    analytics_triggered: bool = Field(default=False, description="분석 트리거 여부")


class BoardAnalyticsRequest(BaseModel):
    """보드 분석 요청 스키마"""
    board_id: int = Field(..., description="분석할 보드 ID")
    force_refresh: bool = Field(default=False, description="강제 재분석 여부")


class BoardAnalyticsResponse(BaseModel):
    """보드 분석 응답 스키마"""
    board_id: int = Field(..., description="보드 ID")
    content_summary: Optional[str] = Field(None, description="보드 전체 요약")
    dominant_categories: Dict[str, int] = Field(default_factory=dict, description="주요 카테고리 분포")
    tag_distribution: Dict[str, float] = Field(default_factory=dict, description="태그 분포")
    
    # 통계 정보
    total_items: int = Field(..., description="총 아이템 수")
    total_content_length: int = Field(..., description="전체 콘텐츠 길이")
    avg_item_relevance: float = Field(..., description="평균 아이템 관련도")
    
    # 품질 지표
    content_diversity_score: Optional[float] = Field(None, description="콘텐츠 다양성 점수")
    topic_coherence_score: Optional[float] = Field(None, description="주제 일관성 점수")
    
    # 메타데이터
    analytics_version: str = Field(..., description="분석 알고리즘 버전")
    last_analyzed_at: datetime = Field(..., description="마지막 분석 시간")
    is_stale: bool = Field(..., description="분석 결과가 오래되었는지 여부")


class BoardListResponse(BaseModel):
    """보드 목록 응답 스키마"""
    boards: List[Dict[str, Any]] = Field(..., description="보드 목록")
    total_count: int = Field(..., description="총 보드 수")
    analyzed_count: int = Field(..., description="분석 완료된 보드 수")