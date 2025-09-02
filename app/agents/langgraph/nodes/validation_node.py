"""
검증 노드

생성된 결과의 품질을 검증하고 개선 제안을 수행합니다.
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.ai.providers.router import ai_router
from app.monitoring.langsmith.tracer import trace_ai_operation
from ..state import AgentState
from .base_node import BaseNode

logger = get_logger(__name__)


class ValidationNode(BaseNode):
    """검증 노드"""
    
    def __init__(self):
        super().__init__("validation")
    
    def get_node_type(self) -> str:
        return "validation"
    
    @trace_ai_operation("validation")
    async def process(self, state: AgentState, session: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        결과 검증 처리
        
        Args:
            state: 에이전트 상태
            session: 데이터베이스 세션
            
        Returns:
            검증 결과 및 개선 제안
        """
        # 이전 노드들의 결과 수집
        content_analysis = state["results"].get("content_analysis", {})
        tag_extraction = state["results"].get("tag_extraction", {})
        category_classification = state["results"].get("category_classification", {})
        
        if not content_analysis:
            raise ValueError("검증할 콘텐츠 분석 결과가 없습니다.")
        
        user_preferences = state["user_preferences"]
        
        try:
            # 모델 선택 (검증은 좀 더 좋은 모델 사용)
            model_name = await self._select_validation_model(user_preferences)
            
            # 각 결과 요소 검증
            validation_results = {}
            
            # 1. 요약 품질 검증
            summary_validation = await self._validate_summary(
                summary=content_analysis.get("summary", ""),
                original_content=state["input_data"],
                model_name=model_name,
                user_id=state["user_id"],
                session=session
            )
            validation_results["summary"] = summary_validation
            
            # 2. 태그 관련성 검증 (태그가 있는 경우)
            if tag_extraction and tag_extraction.get("tags"):
                tag_validation = await self._validate_tags(
                    tags=tag_extraction.get("tags", []),
                    summary=content_analysis.get("summary", ""),
                    model_name=model_name,
                    user_id=state["user_id"],
                    session=session
                )
                validation_results["tags"] = tag_validation
            
            # 3. 카테고리 적절성 검증 (카테고리가 있는 경우)
            if category_classification and category_classification.get("category"):
                category_validation = await self._validate_category(
                    category=category_classification.get("category", ""),
                    summary=content_analysis.get("summary", ""),
                    tags=tag_extraction.get("tags", []),
                    model_name=model_name,
                    user_id=state["user_id"],
                    session=session
                )
                validation_results["category"] = category_validation
            
            # 4. 전체적 일관성 검증
            consistency_validation = await self._validate_consistency(
                content_analysis=content_analysis,
                tag_extraction=tag_extraction,
                category_classification=category_classification,
                model_name=model_name,
                user_id=state["user_id"],
                session=session
            )
            validation_results["consistency"] = consistency_validation
            
            # 5. 종합 점수 계산
            overall_score = self._calculate_overall_score(validation_results)
            
            # 6. 개선 제안 생성
            improvement_suggestions = self._generate_improvement_suggestions(validation_results, overall_score)
            
            # 토큰 사용량 추정
            estimated_tokens = self._estimate_validation_tokens(validation_results)
            
            result = {
                "validation_results": validation_results,
                "overall_score": overall_score,
                "improvement_suggestions": improvement_suggestions,
                "validation_passed": overall_score >= 0.7,
                "model_used": model_name,
                "tokens_used": estimated_tokens,
                "wtu_consumed": estimated_tokens * 0.001,
                "cost_usd": estimated_tokens * 0.0001,
                "validation_metadata": {
                    "validation_criteria": ["summary_quality", "tag_relevance", "category_appropriateness", "consistency"],
                    "threshold_score": 0.7,
                    "detailed_scores": {k: v.get("score", 0) for k, v in validation_results.items()},
                    "needs_improvement": overall_score < 0.7
                }
            }
            
            logger.info(
                f"Validation completed: overall_score={overall_score:.2f}, "
                f"passed={result['validation_passed']}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            raise
    
    async def _validate_summary(self,
                               summary: str,
                               original_content: Dict[str, Any],
                               model_name: str,
                               user_id: int,
                               session: Optional[AsyncSession]) -> Dict[str, Any]:
        """요약 품질 검증"""
        validation_prompt = f"""
        다음 요약의 품질을 평가해주세요:
        
        요약: {summary}
        
        평가 기준:
        1. 핵심 내용 포함 여부 (0-1)
        2. 간결성 (0-1)
        3. 명확성 (0-1)
        4. 한국어 문법 정확성 (0-1)
        
        JSON 형식으로 응답해주세요:
        {{
            "core_content_score": 0.8,
            "conciseness_score": 0.9,
            "clarity_score": 0.7,
            "grammar_score": 0.9,
            "feedback": "간단한 피드백"
        }}
        """
        
        messages = [
            {"role": "system", "content": "당신은 콘텐츠 품질 평가 전문가입니다."},
            {"role": "user", "content": validation_prompt}
        ]
        
        response = await ai_router.generate_chat_completion(
            messages=messages,
            model=model_name,
            max_tokens=300,
            temperature=0.1,
            user_id=user_id,
            session=session
        )
        
        try:
            import json
            validation_data = json.loads(response.content)
            # 전체 점수 계산
            scores = [
                validation_data.get("core_content_score", 0.5),
                validation_data.get("conciseness_score", 0.5),
                validation_data.get("clarity_score", 0.5),
                validation_data.get("grammar_score", 0.5)
            ]
            validation_data["score"] = sum(scores) / len(scores)
            return validation_data
        except (json.JSONDecodeError, KeyError):
            # JSON 파싱 실패 시 기본값 반환
            return {
                "score": 0.6,
                "feedback": "검증 중 오류 발생",
                "core_content_score": 0.6,
                "conciseness_score": 0.6,
                "clarity_score": 0.6,
                "grammar_score": 0.6
            }
    
    async def _validate_tags(self,
                           tags: List[str],
                           summary: str,
                           model_name: str,
                           user_id: int,
                           session: Optional[AsyncSession]) -> Dict[str, Any]:
        """태그 관련성 검증"""
        tags_str = ", ".join(tags)
        
        validation_prompt = f"""
        다음 요약과 태그의 관련성을 평가해주세요:
        
        요약: {summary}
        태그: {tags_str}
        
        평가 기준:
        1. 태그와 요약 내용의 관련성 (0-1)
        2. 태그의 적절성 (0-1)
        3. 태그의 다양성 (0-1)
        
        JSON 형식으로 응답:
        {{
            "relevance_score": 0.8,
            "appropriateness_score": 0.9,
            "diversity_score": 0.7,
            "feedback": "피드백"
        }}
        """
        
        messages = [
            {"role": "system", "content": "당신은 태그 품질 평가 전문가입니다."},
            {"role": "user", "content": validation_prompt}
        ]
        
        response = await ai_router.generate_chat_completion(
            messages=messages,
            model=model_name,
            max_tokens=200,
            temperature=0.1,
            user_id=user_id,
            session=session
        )
        
        try:
            import json
            validation_data = json.loads(response.content)
            scores = [
                validation_data.get("relevance_score", 0.5),
                validation_data.get("appropriateness_score", 0.5),
                validation_data.get("diversity_score", 0.5)
            ]
            validation_data["score"] = sum(scores) / len(scores)
            return validation_data
        except (json.JSONDecodeError, KeyError):
            return {
                "score": 0.6,
                "feedback": "태그 검증 중 오류 발생",
                "relevance_score": 0.6,
                "appropriateness_score": 0.6,
                "diversity_score": 0.6
            }
    
    async def _validate_category(self,
                               category: str,
                               summary: str,
                               tags: List[str],
                               model_name: str,
                               user_id: int,
                               session: Optional[AsyncSession]) -> Dict[str, Any]:
        """카테고리 적절성 검증"""
        tags_str = ", ".join(tags) if tags else "없음"
        
        validation_prompt = f"""
        다음 콘텐츠의 카테고리 분류가 적절한지 평가해주세요:
        
        요약: {summary}
        태그: {tags_str}
        분류된 카테고리: {category}
        
        평가 기준:
        1. 카테고리와 내용의 일치도 (0-1)
        2. 카테고리의 구체성 (0-1)
        
        JSON 형식으로 응답:
        {{
            "match_score": 0.8,
            "specificity_score": 0.7,
            "feedback": "피드백"
        }}
        """
        
        messages = [
            {"role": "system", "content": "당신은 콘텐츠 분류 전문가입니다."},
            {"role": "user", "content": validation_prompt}
        ]
        
        response = await ai_router.generate_chat_completion(
            messages=messages,
            model=model_name,
            max_tokens=150,
            temperature=0.1,
            user_id=user_id,
            session=session
        )
        
        try:
            import json
            validation_data = json.loads(response.content)
            scores = [
                validation_data.get("match_score", 0.5),
                validation_data.get("specificity_score", 0.5)
            ]
            validation_data["score"] = sum(scores) / len(scores)
            return validation_data
        except (json.JSONDecodeError, KeyError):
            return {
                "score": 0.6,
                "feedback": "카테고리 검증 중 오류 발생",
                "match_score": 0.6,
                "specificity_score": 0.6
            }
    
    async def _validate_consistency(self,
                                  content_analysis: Dict[str, Any],
                                  tag_extraction: Dict[str, Any],
                                  category_classification: Dict[str, Any],
                                  model_name: str,
                                  user_id: int,
                                  session: Optional[AsyncSession]) -> Dict[str, Any]:
        """전체적 일관성 검증"""
        # 간단한 휴리스틱 기반 일관성 검사
        consistency_score = 0.8  # 기본 점수
        
        # 태그와 카테고리 간의 관련성 체크
        if tag_extraction and category_classification:
            tags = tag_extraction.get("tags", [])
            category = category_classification.get("category", "")
            
            # 간단한 키워드 매칭 체크
            category_words = category.lower().split()
            tag_words = [tag.lower() for tag in tags]
            
            # 교집합이 있으면 일관성 점수 증가
            if any(word in tag_words for word in category_words):
                consistency_score += 0.1
        
        return {
            "score": min(1.0, consistency_score),
            "feedback": "결과 간 일관성이 양호합니다." if consistency_score > 0.7 else "결과 간 일관성을 개선할 필요가 있습니다."
        }
    
    def _calculate_overall_score(self, validation_results: Dict[str, Any]) -> float:
        """종합 점수 계산"""
        scores = []
        weights = {
            "summary": 0.4,
            "tags": 0.2,
            "category": 0.2,
            "consistency": 0.2
        }
        
        for key, result in validation_results.items():
            if isinstance(result, dict) and "score" in result:
                weight = weights.get(key, 0.25)
                scores.append(result["score"] * weight)
        
        return sum(scores) / sum(weights.get(key, 0.25) for key in validation_results.keys()) if scores else 0.5
    
    def _generate_improvement_suggestions(self, validation_results: Dict[str, Any], overall_score: float) -> List[str]:
        """개선 제안 생성"""
        suggestions = []
        
        if overall_score < 0.7:
            suggestions.append("전체적인 결과 품질이 기준에 못 미치므로 재처리를 권장합니다.")
        
        # 각 영역별 개선 제안
        for area, result in validation_results.items():
            if isinstance(result, dict) and result.get("score", 1.0) < 0.6:
                if area == "summary":
                    suggestions.append("요약의 명확성과 간결성을 개선하세요.")
                elif area == "tags":
                    suggestions.append("더 관련성 높고 구체적인 태그를 생성하세요.")
                elif area == "category":
                    suggestions.append("더 적절하고 구체적인 카테고리를 선택하세요.")
                elif area == "consistency":
                    suggestions.append("요약, 태그, 카테고리 간의 일관성을 개선하세요.")
        
        return suggestions if suggestions else ["결과가 양호합니다."]
    
    def _estimate_validation_tokens(self, validation_results: Dict[str, Any]) -> int:
        """검증 과정에서 사용된 토큰 수 추정"""
        # 각 검증 단계별 대략적인 토큰 수
        base_tokens = 100  # 기본 시스템 메시지 등
        validation_tokens = len(validation_results) * 200  # 각 검증당 약 200토큰
        return base_tokens + validation_tokens
    
    async def _select_validation_model(self, user_preferences) -> str:
        """검증용 모델 선택 (일반적으로 더 좋은 모델 사용)"""
        default_model = "gpt-4o"  # 검증은 좀 더 정확한 모델 사용
        
        if user_preferences.default_llm_model and "gpt-4" in user_preferences.default_llm_model:
            return user_preferences.default_llm_model
        
        # 비용 민감도가 매우 높은 경우에만 mini 모델 사용
        if user_preferences.cost_sensitivity == "high" and user_preferences.quality_preference == "speed":
            return "gpt-4o-mini"
        
        return default_model