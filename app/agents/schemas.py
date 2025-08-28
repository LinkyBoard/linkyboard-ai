"""
Agent 시스템 스키마 정의
"""

from typing import Dict, Any, Optional, List, Literal, Tuple
from datetime import datetime
from pydantic import BaseModel, Field


class ProcessingModeRequest(BaseModel):
    """처리 모드 선택 요청"""
    mode: Literal["legacy", "agent", "auto"] = Field("auto", description="처리 모드 선택")
    user_id: int = Field(..., description="사용자 ID")
    board_id: Optional[int] = Field(None, description="보드 ID (선택사항)")
    task_type: str = Field("general", description="작업 유형 (board_analysis, clipper, summary 등)")
    complexity_preference: Literal["fast", "balanced", "thorough"] = Field("balanced", description="복잡도 선호도")
    quality_threshold: float = Field(0.85, description="최소 품질 임계값 (0.0-1.0)")
    budget_limit_wtu: Optional[float] = Field(None, description="WTU 예산 한계")


class ProcessingModeResponse(BaseModel):
    """처리 모드 응답"""
    selected_mode: str = Field(..., description="선택된 모드")
    reason: str = Field(..., description="선택 이유")
    estimated_time_seconds: int = Field(..., description="예상 처리 시간 (초)")
    estimated_wtu: float = Field(..., description="예상 WTU 소비량")
    quality_expectation: float = Field(..., description="예상 품질 점수 (0.0-1.0)")
    cost_efficiency_score: float = Field(..., description="비용 효율성 점수 (0.0-1.0)")
    recommended_models: List[str] = Field(default_factory=list, description="추천 모델 목록")
    fallback_available: bool = Field(True, description="폴백 모드 사용 가능 여부")


class TrustScore(BaseModel):
    """신뢰도 점수 상세"""
    semantic_similarity: float = Field(..., description="의미적 유사도 (0-1)", ge=0.0, le=1.0)
    factual_consistency: float = Field(..., description="사실 일치도 (0-1)", ge=0.0, le=1.0) 
    completeness: float = Field(..., description="완성도 (0-1)", ge=0.0, le=1.0)
    overall_trust: float = Field(..., description="종합 신뢰도 (0-1)", ge=0.0, le=1.0)
    reference_coverage: float = Field(..., description="레퍼런스 커버리지 (0-1)", ge=0.0, le=1.0)
    confidence_interval: Tuple[float, float] = Field(..., description="신뢰구간 (하한, 상한)")
    validation_details: Dict[str, Any] = Field(default_factory=dict, description="검증 상세 정보")


class ReferenceValidation(BaseModel):
    """레퍼런스 기반 검증 정보"""
    materials_used: int = Field(..., description="사용된 레퍼런스 자료 수", ge=0)
    coverage_score: float = Field(..., description="커버리지 점수", ge=0.0, le=1.0)
    confidence_level: Tuple[float, float] = Field(..., description="신뢰 수준")
    validation_method: str = Field("reference_based", description="검증 방법")
    reference_sources: List[str] = Field(default_factory=list, description="레퍼런스 소스 목록")


class UserModelPreferences(BaseModel):
    """사용자 모델 선호도"""
    user_id: int = Field(..., description="사용자 ID")
    default_llm_model: Optional[str] = Field(None, description="기본 LLM 모델")
    budget_limit_wtu: Optional[float] = Field(None, description="WTU 예산 한계")
    quality_preference: Literal["speed", "balanced", "quality"] = Field("balanced", description="품질 선호도")
    cost_sensitivity: Literal["low", "medium", "high"] = Field("medium", description="비용 민감도")
    preferred_providers: List[str] = Field(default_factory=list, description="선호 제공자 목록")
    avoid_models: List[str] = Field(default_factory=list, description="피할 모델 목록")


class AgentContext(BaseModel):
    """에이전트 실행 컨텍스트"""
    user_id: int = Field(..., description="사용자 ID")
    board_id: Optional[int] = Field(None, description="보드 ID")
    session_id: str = Field(..., description="세션 ID")
    task_type: str = Field(..., description="작업 유형")
    complexity: int = Field(1, description="작업 복잡도 (1-5)", ge=1, le=5)
    user_model_preferences: UserModelPreferences = Field(..., description="사용자 모델 선호도")
    reference_materials: List[str] = Field(default_factory=list, description="레퍼런스 자료")


class ExecutionSummary(BaseModel):
    """실행 요약"""
    total_time_ms: int = Field(..., description="총 실행 시간 (밀리초)")
    total_wtu_consumed: float = Field(..., description="총 WTU 소비량")
    models_used: List[str] = Field(..., description="사용된 모델 목록")
    quality_score: float = Field(..., description="품질 점수")
    agents_executed: List[str] = Field(..., description="실행된 에이전트 목록")
    success_rate: float = Field(..., description="성공률")


class ModePerformanceMetrics(BaseModel):
    """모드별 성능 메트릭"""
    mode: str = Field(..., description="모드명")
    avg_response_time: float = Field(..., description="평균 응답 시간")
    avg_wtu_consumption: float = Field(..., description="평균 WTU 소비량")
    avg_quality_score: float = Field(..., description="평균 품질 점수")
    avg_trust_score: float = Field(..., description="평균 신뢰도 점수")
    user_satisfaction: float = Field(..., description="사용자 만족도")
    success_rate: float = Field(..., description="성공률")
    cost_efficiency: float = Field(..., description="비용 효율성")


class ModeComparisonAnalytics(BaseModel):
    """모드 비교 분석"""
    legacy_mode_stats: ModePerformanceMetrics = Field(..., description="V1 Legacy 모드 통계")
    agent_mode_stats: ModePerformanceMetrics = Field(..., description="V2 Agent 모드 통계")
    improvement_metrics: Dict[str, float] = Field(..., description="개선 지표")
    recommendation: str = Field(..., description="추천 모드")
    confidence_score: float = Field(..., description="추천 신뢰도")


class DateRange(BaseModel):
    """날짜 범위"""
    start_date: datetime = Field(..., description="시작 날짜")
    end_date: datetime = Field(..., description="종료 날짜")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }