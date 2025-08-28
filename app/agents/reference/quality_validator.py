"""
Quality Validator - 품질 검증기

레퍼런스 자료를 기반으로 AI 응답의 품질과 신뢰도를 검증합니다.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import re
import json
from dataclasses import dataclass

from app.core.logging import get_logger
from app.ai.providers.router import ai_router
from ..schemas import TrustScore, ReferenceValidation
from .reference_manager import ReferenceManager, ReferenceMaterial

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """검증 결과"""
    trust_score: TrustScore
    validation_details: Dict[str, Any]
    recommendations: List[str]
    issues_found: List[str]
    passed: bool


class QualityValidator:
    """품질 검증기"""
    
    def __init__(self, reference_manager: ReferenceManager):
        self.reference_manager = reference_manager
        self.validation_cache: Dict[str, ValidationResult] = {}
        
    async def validate_against_references(
        self,
        ai_response: str,
        user_id: int,
        reference_materials: Optional[List[str]] = None,
        validation_model: str = "gpt-4o-mini",
        context_info: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        레퍼런스 자료와 AI 응답을 비교하여 품질 검증
        
        Args:
            ai_response: 검증할 AI 응답
            user_id: 사용자 ID
            reference_materials: 사용할 레퍼런스 자료 ID 목록 (None이면 자동 선택)
            validation_model: 검증에 사용할 모델
            context_info: 추가 컨텍스트 정보
            
        Returns:
            검증 결과
        """
        try:
            logger.info(f"Starting quality validation for user {user_id}")
            
            # 1. 레퍼런스 자료 선택
            if reference_materials:
                materials = []
                for material_id in reference_materials:
                    material = await self.reference_manager.get_reference_material(
                        material_id, user_id
                    )
                    if material:
                        materials.append(material)
            else:
                # 자동 선택: AI 응답과 관련성 높은 자료들
                materials = await self._select_relevant_materials(ai_response, user_id)
            
            if not materials:
                logger.warning("No reference materials available for validation")
                return self._create_default_validation_result(
                    "레퍼런스 자료가 없어 검증을 수행할 수 없습니다."
                )
            
            logger.info(f"Using {len(materials)} reference materials for validation")
            
            # 2. 각 검증 요소별 점수 계산
            semantic_score = await self._calculate_semantic_similarity(
                ai_response, materials, validation_model
            )
            
            factual_score = await self._check_factual_consistency(
                ai_response, materials, validation_model
            )
            
            completeness_score = await self._assess_completeness(
                ai_response, materials, validation_model
            )
            
            coverage_score = await self._calculate_reference_coverage(
                ai_response, materials
            )
            
            # 3. 종합 신뢰도 점수 계산
            overall_trust = self._calculate_overall_trust_score(
                semantic_score, factual_score, completeness_score, coverage_score
            )
            
            # 4. 신뢰 구간 계산
            confidence_interval = self._calculate_confidence_interval(
                [semantic_score, factual_score, completeness_score, coverage_score]
            )
            
            # 5. 검증 상세 정보 및 추천사항 생성
            validation_details, recommendations, issues = await self._generate_validation_insights(
                ai_response, materials, {
                    'semantic': semantic_score,
                    'factual': factual_score, 
                    'completeness': completeness_score,
                    'coverage': coverage_score
                }
            )
            
            # 6. TrustScore 생성
            trust_score = TrustScore(
                semantic_similarity=semantic_score,
                factual_consistency=factual_score,
                completeness=completeness_score,
                overall_trust=overall_trust,
                reference_coverage=coverage_score,
                confidence_interval=confidence_interval,
                validation_details=validation_details
            )
            
            # 7. 최종 검증 결과
            validation_result = ValidationResult(
                trust_score=trust_score,
                validation_details=validation_details,
                recommendations=recommendations,
                issues_found=issues,
                passed=overall_trust >= 0.7  # 70% 이상을 통과로 판정
            )
            
            logger.info(f"Validation completed: overall_trust={overall_trust:.3f}, passed={validation_result.passed}")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Quality validation failed: {e}")
            return self._create_default_validation_result(f"검증 중 오류 발생: {str(e)}")
    
    async def _select_relevant_materials(
        self,
        ai_response: str,
        user_id: int,
        max_materials: int = 5
    ) -> List[ReferenceMaterial]:
        """AI 응답과 관련성 높은 레퍼런스 자료 선택"""
        try:
            # 키워드 추출
            keywords = self._extract_keywords(ai_response)
            
            if not keywords:
                # 키워드가 없으면 최신 자료들 사용
                all_materials = await self.reference_manager.get_user_materials(
                    user_id, limit=max_materials
                )
                return all_materials
            
            # 각 키워드로 검색하여 관련 자료 찾기
            relevant_materials = {}
            
            for keyword in keywords[:10]:  # 최대 10개 키워드만 사용
                search_results = await self.reference_manager.search_materials(
                    user_id, keyword, limit=3
                )
                
                for material, score in search_results:
                    if material.material_id in relevant_materials:
                        relevant_materials[material.material_id] = (
                            material,
                            relevant_materials[material.material_id][1] + score
                        )
                    else:
                        relevant_materials[material.material_id] = (material, score)
            
            # 점수순으로 정렬하여 상위 자료들 반환
            sorted_materials = sorted(
                relevant_materials.values(),
                key=lambda x: x[1],
                reverse=True
            )
            
            return [material for material, _ in sorted_materials[:max_materials]]
            
        except Exception as e:
            logger.error(f"Failed to select relevant materials: {e}")
            return []
    
    def _extract_keywords(self, text: str, max_keywords: int = 20) -> List[str]:
        """텍스트에서 키워드 추출 (간단한 구현)"""
        try:
            # 간단한 키워드 추출 (실제로는 NLP 라이브러리 사용)
            
            # 특수문자 제거 및 소문자 변환
            clean_text = re.sub(r'[^\w\s]', ' ', text.lower())
            words = clean_text.split()
            
            # 불용어 제거 (간단한 목록)
            stop_words = {
                '그리고', '하지만', '또한', '그러나', '따라서', '그래서', '그런데',
                '이것', '그것', '저것', '이러한', '그러한', '저러한', '있는', '없는',
                'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of',
                'with', 'by', 'this', 'that', 'these', 'those', 'is', 'are', 'was', 'were'
            }
            
            # 의미있는 단어들만 추출 (길이 3 이상)
            keywords = [
                word for word in words 
                if len(word) >= 3 and word not in stop_words
            ]
            
            # 빈도순으로 정렬
            word_freq = {}
            for word in keywords:
                word_freq[word] = word_freq.get(word, 0) + 1
            
            sorted_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            
            return [word for word, _ in sorted_keywords[:max_keywords]]
            
        except Exception as e:
            logger.warning(f"Keyword extraction failed: {e}")
            return []
    
    async def _calculate_semantic_similarity(
        self,
        ai_response: str,
        materials: List[ReferenceMaterial],
        model: str
    ) -> float:
        """의미적 유사도 계산"""
        try:
            if not materials:
                return 0.5  # 기본값
            
            # 레퍼런스 자료 요약
            reference_summary = self._summarize_materials(materials)
            
            # AI 모델을 사용한 의미적 유사도 평가
            system_prompt = """당신은 텍스트 유사도 분석 전문가입니다. 
주어진 AI 응답과 레퍼런스 자료의 의미적 유사도를 0.0~1.0 사이의 점수로 평가해주세요.

평가 기준:
- 0.9-1.0: 거의 동일한 의미
- 0.7-0.8: 매우 유사한 의미
- 0.5-0.6: 부분적으로 유사
- 0.3-0.4: 약간 관련
- 0.0-0.2: 관련성 없음

점수만 반환해주세요."""
            
            user_prompt = f"""AI 응답:
{ai_response[:2000]}

레퍼런스 자료:
{reference_summary[:2000]}

유사도 점수:"""
            
            response = await ai_router.chat_completion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=50
            )
            
            # 점수 추출
            score_text = response.get('content', '0.5')
            score_match = re.search(r'(\d+\.?\d*)', score_text)
            
            if score_match:
                score = float(score_match.group(1))
                return max(0.0, min(1.0, score))
            else:
                return 0.5
                
        except Exception as e:
            logger.error(f"Semantic similarity calculation failed: {e}")
            return 0.5
    
    async def _check_factual_consistency(
        self,
        ai_response: str,
        materials: List[ReferenceMaterial],
        model: str
    ) -> float:
        """사실 일치도 확인"""
        try:
            if not materials:
                return 0.5
            
            reference_summary = self._summarize_materials(materials)
            
            system_prompt = """당신은 사실 검증 전문가입니다. 
AI 응답의 내용이 레퍼런스 자료와 얼마나 사실적으로 일치하는지 평가해주세요.

평가 기준:
- 1.0: 모든 사실이 정확히 일치
- 0.8: 대부분의 사실이 일치하고 오류 없음
- 0.6: 주요 사실은 일치하지만 세부사항에 차이
- 0.4: 일부 사실만 일치하고 오류 포함  
- 0.2: 많은 사실 오류 또는 불일치
- 0.0: 대부분 사실 오류

점수만 반환해주세요."""
            
            user_prompt = f"""AI 응답:
{ai_response[:2000]}

레퍼런스 자료:
{reference_summary[:2000]}

사실 일치도 점수:"""
            
            response = await ai_router.chat_completion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=50
            )
            
            score_text = response.get('content', '0.5')
            score_match = re.search(r'(\d+\.?\d*)', score_text)
            
            if score_match:
                score = float(score_match.group(1))
                return max(0.0, min(1.0, score))
            else:
                return 0.5
                
        except Exception as e:
            logger.error(f"Factual consistency check failed: {e}")
            return 0.5
    
    async def _assess_completeness(
        self,
        ai_response: str,
        materials: List[ReferenceMaterial],
        model: str
    ) -> float:
        """완성도 평가"""
        try:
            # 간단한 완성도 평가 (응답 길이, 구조 등)
            response_length = len(ai_response)
            
            # 기본 점수 (응답 길이에 따라)
            if response_length < 100:
                length_score = 0.3
            elif response_length < 500:
                length_score = 0.6
            elif response_length < 2000:
                length_score = 0.8
            else:
                length_score = 0.9
                
            # 구조화 정도 (문단, 리스트 등)
            structure_score = 0.5
            if re.search(r'\n\n', ai_response):  # 문단 구분
                structure_score += 0.1
            if re.search(r'^\s*[-\*\d+]', ai_response, re.MULTILINE):  # 리스트
                structure_score += 0.1
            if re.search(r'[?!.]', ai_response):  # 구두점
                structure_score += 0.1
                
            # 키워드 커버리지
            material_keywords = set()
            for material in materials:
                material_keywords.update(self._extract_keywords(material.content, 10))
            
            response_keywords = set(self._extract_keywords(ai_response, 20))
            
            if material_keywords:
                coverage_ratio = len(material_keywords & response_keywords) / len(material_keywords)
                coverage_score = min(1.0, coverage_ratio * 2)  # 50% 커버리지를 1.0으로 정규화
            else:
                coverage_score = 0.5
                
            # 가중 평균
            final_score = (length_score * 0.3 + structure_score * 0.3 + coverage_score * 0.4)
            return max(0.0, min(1.0, final_score))
            
        except Exception as e:
            logger.error(f"Completeness assessment failed: {e}")
            return 0.5
    
    async def _calculate_reference_coverage(
        self,
        ai_response: str,
        materials: List[ReferenceMaterial]
    ) -> float:
        """레퍼런스 커버리지 계산"""
        try:
            if not materials:
                return 0.0
            
            total_materials = len(materials)
            referenced_count = 0
            
            response_lower = ai_response.lower()
            
            for material in materials:
                material_keywords = self._extract_keywords(material.content, 5)
                
                # 자료의 주요 키워드가 응답에 포함되어 있는지 확인
                keyword_found = any(
                    keyword.lower() in response_lower 
                    for keyword in material_keywords
                )
                
                if keyword_found:
                    referenced_count += 1
            
            coverage_ratio = referenced_count / total_materials if total_materials > 0 else 0.0
            return coverage_ratio
            
        except Exception as e:
            logger.error(f"Reference coverage calculation failed: {e}")
            return 0.0
    
    def _calculate_overall_trust_score(
        self,
        semantic: float,
        factual: float,
        completeness: float,
        coverage: float
    ) -> float:
        """종합 신뢰도 점수 계산"""
        # 가중 평균 (사실 일치도와 의미적 유사도를 높게 가중)
        weights = {
            'factual': 0.4,      # 사실 정확성이 가장 중요
            'semantic': 0.3,     # 의미적 유사도
            'completeness': 0.2, # 완성도
            'coverage': 0.1      # 레퍼런스 커버리지
        }
        
        overall = (
            semantic * weights['semantic'] +
            factual * weights['factual'] +
            completeness * weights['completeness'] +
            coverage * weights['coverage']
        )
        
        return max(0.0, min(1.0, overall))
    
    def _calculate_confidence_interval(self, scores: List[float]) -> Tuple[float, float]:
        """신뢰 구간 계산"""
        try:
            if not scores:
                return (0.0, 1.0)
            
            mean_score = sum(scores) / len(scores)
            
            # 간단한 신뢰구간 계산 (표준편차 기반)
            variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
            std_dev = variance ** 0.5
            
            margin = std_dev * 1.96  # 95% 신뢰구간
            
            lower = max(0.0, mean_score - margin)
            upper = min(1.0, mean_score + margin)
            
            return (lower, upper)
            
        except Exception as e:
            logger.warning(f"Confidence interval calculation failed: {e}")
            return (0.0, 1.0)
    
    def _summarize_materials(self, materials: List[ReferenceMaterial], max_length: int = 1000) -> str:
        """레퍼런스 자료들을 요약"""
        try:
            summary_parts = []
            
            for i, material in enumerate(materials[:5]):  # 최대 5개 자료만
                content = material.content[:200] + "..." if len(material.content) > 200 else material.content
                summary_parts.append(f"[자료 {i+1}: {material.title}]\n{content}")
            
            full_summary = "\n\n".join(summary_parts)
            
            if len(full_summary) > max_length:
                return full_summary[:max_length] + "..."
            
            return full_summary
            
        except Exception as e:
            logger.error(f"Material summarization failed: {e}")
            return "레퍼런스 자료 요약 실패"
    
    async def _generate_validation_insights(
        self,
        ai_response: str,
        materials: List[ReferenceMaterial],
        scores: Dict[str, float]
    ) -> Tuple[Dict[str, Any], List[str], List[str]]:
        """검증 인사이트 생성"""
        try:
            validation_details = {
                'materials_count': len(materials),
                'response_length': len(ai_response),
                'validation_timestamp': datetime.now().isoformat(),
                'score_breakdown': scores
            }
            
            recommendations = []
            issues = []
            
            # 점수 기반 추천사항 및 문제점 식별
            if scores['semantic'] < 0.6:
                issues.append("AI 응답이 레퍼런스 자료와 의미적으로 크게 다름")
                recommendations.append("레퍼런스 자료의 핵심 내용을 더 반영하도록 개선 필요")
            
            if scores['factual'] < 0.7:
                issues.append("사실 정확성에 문제가 있을 수 있음")
                recommendations.append("레퍼런스 자료의 사실 정보를 더 정확히 반영 필요")
            
            if scores['completeness'] < 0.6:
                issues.append("응답의 완성도가 부족함")
                recommendations.append("더 구체적이고 완전한 답변 제공 필요")
            
            if scores['coverage'] < 0.3:
                issues.append("제공된 레퍼런스 자료가 충분히 활용되지 않음")
                recommendations.append("더 많은 레퍼런스 자료 내용을 참고하여 답변 보완")
            
            # 긍정적 피드백도 추가
            if scores['factual'] >= 0.8:
                recommendations.append("사실 정확성이 우수함")
            
            if scores['semantic'] >= 0.8:
                recommendations.append("레퍼런스 자료와의 일관성이 높음")
            
            return validation_details, recommendations, issues
            
        except Exception as e:
            logger.error(f"Validation insights generation failed: {e}")
            return {}, ["검증 인사이트 생성 실패"], ["검증 과정에서 오류 발생"]
    
    def _create_default_validation_result(self, error_message: str) -> ValidationResult:
        """기본 검증 결과 생성"""
        trust_score = TrustScore(
            semantic_similarity=0.5,
            factual_consistency=0.5,
            completeness=0.5,
            overall_trust=0.5,
            reference_coverage=0.0,
            confidence_interval=(0.0, 1.0),
            validation_details={'error': error_message}
        )
        
        return ValidationResult(
            trust_score=trust_score,
            validation_details={'error': error_message},
            recommendations=["레퍼런스 자료를 추가하여 검증 정확도 향상"],
            issues_found=[error_message],
            passed=False
        )


# 글로벌 품질 검증기 인스턴스는 __init__.py에서 관리