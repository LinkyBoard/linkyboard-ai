"""
카테고리 분류 노드

콘텐츠 요약을 바탕으로 적절한 카테고리를 분류합니다.
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.ai.providers.router import ai_router
from app.monitoring.langsmith.tracer import trace_ai_operation
from ..state import AgentState
from .base_node import BaseNode

logger = get_logger(__name__)


class CategoryClassificationNode(BaseNode):
    """카테고리 분류 노드"""
    
    def __init__(self):
        super().__init__("category_classification")
    
    def get_node_type(self) -> str:
        return "category_classification"
    
    @trace_ai_operation("category_classification")
    async def process(self, state: AgentState, session: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        카테고리 분류 처리
        
        Args:
            state: 에이전트 상태
            session: 데이터베이스 세션
            
        Returns:
            분류된 카테고리 결과
        """
        # 이전 노드의 결과에서 요약 가져오기
        content_analysis_result = state["results"].get("content_analysis")
        if not content_analysis_result:
            raise ValueError("콘텐츠 분석 결과가 없습니다. content_analysis 노드를 먼저 실행해야 합니다.")
        
        summary = content_analysis_result.get("summary", "")
        if not summary:
            raise ValueError("요약 정보가 없습니다.")
        
        user_preferences = state["user_preferences"]
        input_data = state["input_data"]
        
        try:
            # 기존 유사 카테고리 가져오기 (옵션)
            similar_categories = input_data.get("similar_categories", [])
            
            # 모델 선택
            model_name = await self._select_model(user_preferences)
            
            # 콘텐츠 타입에 따른 카테고리 분류
            content_type = content_analysis_result.get("content_type", "webpage")
            
            if content_type == "youtube":
                category = await self._classify_youtube_category(
                    title=input_data.get("title", ""),
                    summary=summary,
                    model_name=model_name,
                    similar_categories=similar_categories,
                    user_id=state["user_id"],
                    session=session
                )
            else:
                category = await self._classify_webpage_category(
                    summary=summary,
                    model_name=model_name,
                    similar_categories=similar_categories,
                    user_id=state["user_id"],
                    session=session
                )
            
            # 카테고리 정제
            refined_category = self._refine_category(category)
            
            # 신뢰도 계산 (간단한 휴리스틱)
            confidence = self._calculate_confidence(summary, refined_category, similar_categories)
            
            # 토큰 사용량 추정
            estimated_input_tokens = len(summary) // 4
            estimated_output_tokens = len(refined_category) // 4
            total_tokens = estimated_input_tokens + estimated_output_tokens
            
            result = {
                "category": refined_category,
                "confidence": confidence,
                "model_used": model_name,
                "tokens_used": total_tokens,
                "wtu_consumed": total_tokens * 0.001,
                "cost_usd": total_tokens * 0.0001,
                "classification_metadata": {
                    "summary_length": len(summary),
                    "similar_categories_count": len(similar_categories),
                    "content_type": content_type,
                    "confidence_level": "high" if confidence > 0.8 else "medium" if confidence > 0.5 else "low"
                }
            }
            
            logger.info(f"Category classification completed: '{refined_category}' with confidence {confidence:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"Category classification failed: {e}")
            raise
    
    async def _classify_webpage_category(self,
                                        summary: str,
                                        model_name: str,
                                        similar_categories: List[str],
                                        user_id: int,
                                        session: Optional[AsyncSession]) -> str:
        """웹페이지 카테고리 분류"""
        return await ai_router.recommend_webpage_category(
            summary=summary,
            similar_categories=similar_categories,
            model=model_name,
            user_id=user_id,
            session=session
        )
    
    async def _classify_youtube_category(self,
                                        title: str,
                                        summary: str,
                                        model_name: str,
                                        similar_categories: List[str],
                                        user_id: int,
                                        session: Optional[AsyncSession]) -> str:
        """YouTube 카테고리 분류"""
        return await ai_router.recommend_youtube_category(
            title=title,
            summary=summary,
            model=model_name,
            user_id=user_id,
            session=session
        )
    
    def _refine_category(self, category: str) -> str:
        """카테고리 정제"""
        if not category:
            return "기타"
        
        # 카테고리 정제: 공백 제거, 첫 글자 대문자
        refined = category.strip()
        if not refined:
            return "기타"
        
        # 너무 긴 카테고리는 잘라내기
        if len(refined) > 50:
            refined = refined[:50].strip()
        
        # 첫 글자 대문자로 변환 (한글/영어 구분)
        if refined and refined[0].isalpha():
            refined = refined[0].upper() + refined[1:]
        
        return refined
    
    def _calculate_confidence(self, summary: str, category: str, similar_categories: List[str]) -> float:
        """분류 신뢰도 계산 (간단한 휴리스틱)"""
        confidence = 0.5  # 기본 신뢰도
        
        # 요약 길이에 따른 신뢰도 조정
        if len(summary) > 200:
            confidence += 0.2
        elif len(summary) < 50:
            confidence -= 0.2
        
        # 기존 유사 카테고리와의 일치도
        if similar_categories:
            category_lower = category.lower()
            for sim_cat in similar_categories:
                if sim_cat.lower() in category_lower or category_lower in sim_cat.lower():
                    confidence += 0.2
                    break
        
        # 카테고리 길이 (너무 짧거나 길면 신뢰도 감소)
        if 3 <= len(category) <= 20:
            confidence += 0.1
        else:
            confidence -= 0.1
        
        # 0.0 ~ 1.0 범위로 제한
        return max(0.0, min(1.0, confidence))
    
    async def _select_model(self, user_preferences) -> str:
        """사용자 선호도에 따른 모델 선택"""
        # 카테고리 분류는 상대적으로 단순한 작업이므로 빠른 모델 우선
        default_model = "gpt-4o-mini"
        
        if user_preferences.default_llm_model:
            return user_preferences.default_llm_model
        
        # 비용 민감도가 높으면 더 저렴한 모델 사용
        if user_preferences.cost_sensitivity == "high":
            return "gpt-4o-mini"
        
        # 품질 선호도가 높으면 더 좋은 모델 사용
        if user_preferences.quality_preference == "quality":
            return "gpt-4o"
        
        return default_model