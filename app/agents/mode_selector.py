"""
Processing Mode Selector - 사용자 처리 모드 선택 및 추천 서비스

V1 (Legacy) vs V2 (Agent) 모드를 자동으로 추천하거나 사용자 선택을 처리합니다.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.metrics import get_user_monthly_wtu
from app.metrics.model_catalog_service import model_catalog_service
from .schemas import (
    ProcessingModeRequest, 
    ProcessingModeResponse, 
    UserModelPreferences,
    ModePerformanceMetrics
)

logger = get_logger(__name__)


class ProcessingModeService:
    """처리 모드 선택 및 추천 서비스"""
    
    def __init__(self):
        self.performance_cache = {}
        self.cache_ttl = 3600  # 1시간 캐시
        self.last_cache_update = None

    async def select_processing_mode(
        self, 
        request: ProcessingModeRequest
    ) -> ProcessingModeResponse:
        """
        사용자 요청에 따른 처리 모드 선택 및 추천
        """
        try:
            logger.info(f"Selecting processing mode for user {request.user_id}, mode: {request.mode}")
            
            if request.mode == "legacy":
                return await self._create_legacy_response(request)
            elif request.mode == "agent":
                return await self._create_agent_response(request)
            else:  # auto mode
                return await self._recommend_optimal_mode(request)
                
        except Exception as e:
            logger.error(f"Failed to select processing mode: {str(e)}")
            # 오류 시 기본값으로 Legacy 모드 반환
            return ProcessingModeResponse(
                selected_mode="legacy",
                reason=f"오류로 인한 안전 모드 선택: {str(e)}",
                estimated_time_seconds=30,
                estimated_wtu=2.0,
                quality_expectation=0.85,
                cost_efficiency_score=0.9,
                recommended_models=["gpt-4o-mini"],
                fallback_available=False
            )

    async def _recommend_optimal_mode(
        self, 
        request: ProcessingModeRequest
    ) -> ProcessingModeResponse:
        """
        사용자 선호도와 상황을 고려한 최적 모드 추천
        """
        try:
            # 1. 사용자 WTU 예산 확인
            current_month = date.today().replace(day=1)  # 현재 월의 첫째 날
            monthly_wtu = await get_user_monthly_wtu(request.user_id, current_month)
            
            # 2. 과거 성능 데이터 조회
            performance_data = await self._get_mode_performance_data(
                request.user_id, request.task_type
            )
            
            # 3. 사용자 모델 선호도 로드
            user_preferences = await self._load_user_preferences(request.user_id)
            
            # 4. 추천 점수 계산
            legacy_score = await self._calculate_mode_score(
                "legacy", request, monthly_wtu, performance_data, user_preferences
            )
            agent_score = await self._calculate_mode_score(
                "agent", request, monthly_wtu, performance_data, user_preferences
            )
            
            # 5. 최적 모드 선택
            if agent_score > legacy_score:
                selected_mode = "agent"
                reason = self._generate_recommendation_reason(
                    "agent", agent_score, legacy_score, request
                )
                return await self._create_agent_response(request, reason)
            else:
                selected_mode = "legacy"
                reason = self._generate_recommendation_reason(
                    "legacy", legacy_score, agent_score, request
                )
                return await self._create_legacy_response(request, reason)
                
        except Exception as e:
            logger.error(f"Failed to recommend optimal mode: {str(e)}")
            # 기본적으로 Legacy 모드 추천
            return await self._create_legacy_response(
                request, 
                f"추천 시스템 오류로 안전한 Legacy 모드 선택: {str(e)}"
            )

    async def _calculate_mode_score(
        self,
        mode: str,
        request: ProcessingModeRequest,
        monthly_wtu: float,
        performance_data: Dict[str, Any],
        user_preferences: UserModelPreferences
    ) -> float:
        """
        모드별 추천 점수 계산
        """
        score = 0.0
        
        # 기본 점수 (Legacy: 7.0, Agent: 6.0 - Legacy가 안정성에서 우위)
        base_scores = {"legacy": 7.0, "agent": 6.0}
        score += base_scores.get(mode, 5.0)
        
        # 복잡도 선호도에 따른 점수
        complexity_bonus = {
            "fast": {"legacy": 2.0, "agent": 0.5},
            "balanced": {"legacy": 1.0, "agent": 1.5},
            "thorough": {"legacy": 0.5, "agent": 2.5}
        }
        score += complexity_bonus.get(request.complexity_preference, {}).get(mode, 0)
        
        # 품질 요구사항에 따른 점수
        if request.quality_threshold >= 0.95:
            score += 2.0 if mode == "agent" else 0.5
        elif request.quality_threshold >= 0.9:
            score += 1.5 if mode == "agent" else 1.0
        else:
            score += 1.0 if mode == "legacy" else 0.8
        
        # WTU 예산 고려
        budget_limit = request.budget_limit_wtu or user_preferences.budget_limit_wtu
        if budget_limit and monthly_wtu > budget_limit * 0.8:  # 예산의 80% 사용시
            score += 1.5 if mode == "legacy" else -1.0  # Legacy가 비용 효율적
        
        # 과거 성능 데이터 반영
        if performance_data:
            legacy_perf = performance_data.get("legacy", {})
            agent_perf = performance_data.get("agent", {})
            
            if mode == "legacy" and legacy_perf.get("success_rate", 0) > 0.95:
                score += 1.0
            elif mode == "agent" and agent_perf.get("avg_quality_score", 0) > 0.9:
                score += 1.5
        
        # 사용자 선호도 반영
        if user_preferences.quality_preference == "quality" and mode == "agent":
            score += 1.0
        elif user_preferences.quality_preference == "speed" and mode == "legacy":
            score += 1.0
        
        # 비용 민감도 반영
        if user_preferences.cost_sensitivity == "high" and mode == "legacy":
            score += 1.0
        elif user_preferences.cost_sensitivity == "low" and mode == "agent":
            score += 0.5
        
        return score

    def _generate_recommendation_reason(
        self,
        selected_mode: str,
        selected_score: float,
        other_score: float,
        request: ProcessingModeRequest
    ) -> str:
        """추천 이유 생성"""
        reasons = []
        
        if selected_mode == "agent":
            reasons.append("높은 품질 요구사항에 적합")
            if request.quality_threshold >= 0.9:
                reasons.append(f"품질 임계값 {request.quality_threshold} 달성 가능")
            if request.complexity_preference == "thorough":
                reasons.append("정밀한 분석 선호도에 맞음")
        else:  # legacy
            reasons.append("안정적이고 검증된 성능")
            if request.complexity_preference == "fast":
                reasons.append("빠른 처리 선호도에 적합")
            reasons.append("비용 효율적")
        
        score_diff = abs(selected_score - other_score)
        if score_diff > 2.0:
            reasons.append("명확한 성능 우위")
        elif score_diff > 1.0:
            reasons.append("적합도 우위")
        else:
            reasons.append("균형적 선택")
            
        return " | ".join(reasons)

    async def _create_legacy_response(
        self, 
        request: ProcessingModeRequest,
        custom_reason: Optional[str] = None
    ) -> ProcessingModeResponse:
        """Legacy 모드 응답 생성"""
        
        # 기본 추정값 (Legacy 모드)
        estimated_time = 15 if request.complexity_preference == "fast" else 30
        estimated_wtu = 1.0 if request.complexity_preference == "fast" else 2.0
        quality_expectation = 0.85 if request.complexity_preference == "fast" else 0.88
        
        reason = custom_reason or f"안정적인 성능과 비용 효율성 ({request.complexity_preference} 모드)"
        
        # 추천 모델 (Legacy에서 주로 사용되는 모델들)
        recommended_models = ["gpt-4o-mini", "gemini-1.5-flash", "claude-3-haiku"]
        
        return ProcessingModeResponse(
            selected_mode="legacy",
            reason=reason,
            estimated_time_seconds=estimated_time,
            estimated_wtu=estimated_wtu,
            quality_expectation=quality_expectation,
            cost_efficiency_score=0.9,
            recommended_models=recommended_models,
            fallback_available=False  # Legacy는 폴백이 아님
        )

    async def _create_agent_response(
        self,
        request: ProcessingModeRequest,
        custom_reason: Optional[str] = None
    ) -> ProcessingModeResponse:
        """Agent 모드 응답 생성"""
        
        # Agent 모드 추정값 (더 높은 품질, 더 많은 리소스)
        complexity_multiplier = {
            "fast": 1.0,
            "balanced": 1.5,
            "thorough": 2.0
        }.get(request.complexity_preference, 1.5)
        
        estimated_time = int(45 * complexity_multiplier)
        estimated_wtu = 3.0 * complexity_multiplier
        quality_expectation = min(0.95, 0.88 + (complexity_multiplier - 1.0) * 0.05)
        
        reason = custom_reason or f"고품질 AI 분석과 검증 시스템 ({request.complexity_preference} 모드)"
        
        # 에이전트에서 사용할 다양한 모델들
        recommended_models = ["gpt-4o", "claude-3.5-sonnet", "gemini-1.5-pro", "gpt-4o-mini"]
        
        return ProcessingModeResponse(
            selected_mode="agent",
            reason=reason,
            estimated_time_seconds=estimated_time,
            estimated_wtu=estimated_wtu,
            quality_expectation=quality_expectation,
            cost_efficiency_score=0.7,  # 높은 품질 대신 낮은 비용 효율성
            recommended_models=recommended_models,
            fallback_available=True  # Agent 실패시 Legacy로 폴백 가능
        )

    async def _get_mode_performance_data(
        self,
        user_id: int,
        task_type: str
    ) -> Dict[str, Any]:
        """
        사용자별, 작업타입별 과거 성능 데이터 조회
        (실제로는 mode_performance_comparison 테이블에서 조회)
        """
        try:
            # 현재는 기본값 반환, 나중에 실제 DB 조회로 대체
            return {
                "legacy": {
                    "avg_response_time": 25.0,
                    "avg_wtu_consumption": 1.8,
                    "avg_quality_score": 0.86,
                    "success_rate": 0.96,
                    "user_satisfaction": 4.1
                },
                "agent": {
                    "avg_response_time": 55.0,
                    "avg_wtu_consumption": 3.2,
                    "avg_quality_score": 0.92,
                    "success_rate": 0.89,
                    "user_satisfaction": 4.4
                }
            }
        except Exception as e:
            logger.warning(f"Failed to get performance data: {str(e)}")
            return {}

    async def _load_user_preferences(self, user_id: int) -> UserModelPreferences:
        """
        사용자 모델 선호도 로드
        (실제로는 user_model_preferences 테이블에서 조회)
        """
        try:
            # 현재는 기본값 반환, 나중에 실제 DB 조회로 대체
            return UserModelPreferences(
                user_id=user_id,
                default_llm_model="gpt-4o-mini",
                budget_limit_wtu=50.0,
                quality_preference="balanced",
                cost_sensitivity="medium",
                preferred_providers=["openai", "anthropic"],
                avoid_models=[]
            )
        except Exception as e:
            logger.warning(f"Failed to load user preferences: {str(e)}")
            return UserModelPreferences(
                user_id=user_id,
                quality_preference="balanced",
                cost_sensitivity="medium"
            )

    async def get_mode_recommendations_for_user(
        self,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        사용자별 모드 사용 패턴 및 추천 분석
        """
        try:
            async with AsyncSessionLocal() as session:
                # 최근 N일간의 모드 사용 패턴 분석
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
                
                # TODO: 실제 DB에서 데이터 조회
                # mode_performance_comparison 테이블 쿼리
                
                # 현재는 모의 데이터 반환
                return {
                    "user_id": user_id,
                    "analysis_period_days": days,
                    "mode_usage_ratio": {
                        "legacy": 0.7,
                        "agent": 0.3
                    },
                    "performance_comparison": {
                        "legacy": {
                            "total_uses": 21,
                            "avg_satisfaction": 4.1,
                            "avg_quality": 0.86,
                            "avg_cost": 1.8
                        },
                        "agent": {
                            "total_uses": 9,
                            "avg_satisfaction": 4.4,
                            "avg_quality": 0.93,
                            "avg_cost": 3.2
                        }
                    },
                    "recommendation": "balanced_usage",
                    "suggested_ratio": {
                        "legacy": 0.6,  # 일반적인 작업
                        "agent": 0.4    # 중요한 분석
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get mode recommendations: {str(e)}")
            return {
                "error": str(e),
                "recommendation": "use_legacy_as_default"
            }


# 싱글톤 인스턴스
mode_selector_service = ProcessingModeService()