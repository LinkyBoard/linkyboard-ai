"""
With AI 서비스 - 모델 선택 지원
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date

from app.metrics.model_catalog_service import model_catalog_service
from app.core.logging import get_logger
from app.metrics import count_tokens

logger = get_logger(__name__)


class WithAIService:
    """With AI 서비스 - 모델 선택 및 WTU 관리"""

    async def ask_with_model_selection(
        self,
        query: str,
        board_id: UUID,
        user_id: int,
        k: int = 4,
        max_out_tokens: int = 800,
        model: Optional[str] = None,
        budget_wtu: Optional[int] = None,
        confidence_target: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        모델 선택을 지원하는 AI 질의
        
        Args:
            query: 질의 내용
            board_id: 보드 ID
            user_id: 사용자 ID
            k: 검색 결과 수
            max_out_tokens: 최대 출력 토큰 수
            model: 요청된 모델 (별칭)
            budget_wtu: 예산 WTU 제한
            confidence_target: 품질 목표
            
        Returns:
            질의 결과와 사용량 정보
        """
        
        # 1. 유효한 모델 결정 (간소화된 버전)
        if model:
            # 요청된 모델이 있으면 해당 모델 사용
            effective_model = await model_catalog_service.get_model_by_alias(model)
        else:
            # 기본 모델 사용 (첫 번째 활성 LLM 모델)
            active_models = await model_catalog_service.get_active_models("llm")
            effective_model = active_models[0] if active_models else None
        
        if not effective_model:
            raise ValueError("No valid model available for this request")
        
        # 2. 예상 WTU 계산 (간소화된 버전)
        input_tokens = count_tokens(query, effective_model.model_name)
        estimated_output_tokens = min(max_out_tokens, 1000)  # 보수적 추정
        
        # 간단한 WTU 계산
        estimated_wtu = int(
            input_tokens * (effective_model.weight_input or 1.0) + 
            estimated_output_tokens * (effective_model.weight_output or 4.0)
        )
        
        # 3. 예산 확인 (간소화된 버전)
        if budget_wtu and estimated_wtu > budget_wtu:
            raise ValueError(f"Budget exceeded: estimated {estimated_wtu} WTU would exceed budget of {budget_wtu}")
        
        # 4. AI 호출 수행 (Mock 구현)
        try:
            if effective_model.model_type == "llm":
                # Mock 응답 생성 (실제 구현에서는 OpenAI API 호출)
                answer = f"""안녕하세요! {effective_model.alias} 모델을 사용하여 답변드립니다.

질문: {query}

이것은 Model Picker v1 테스트용 Mock 응답입니다. 
실제 구현에서는 여기서 OpenAI API를 호출하여 진짜 AI 응답을 생성합니다.

선택된 모델: {effective_model.alias} ({effective_model.provider})
예상 WTU: {estimated_wtu}
"""
                
                actual_output_tokens = count_tokens(answer, effective_model.model_name)
                
                # 실제 WTU 재계산
                actual_wtu = int(
                    input_tokens * (effective_model.weight_input or 1.0) + 
                    actual_output_tokens * (effective_model.weight_output or 4.0)
                )
                
                # 6. 응답 구성
                return {
                    "answer_md": answer,
                    "claims": [],  # 실제로는 검색된 문서들의 클레임
                    "usage": {
                        "in": input_tokens,
                        "cached_in": 0,
                        "out": actual_output_tokens,
                        "embed": 0,
                        "wtu": actual_wtu,
                        "per_model": [{
                            "model": effective_model.alias,
                            "wtu": actual_wtu,
                            "in": input_tokens,
                            "out": actual_output_tokens
                        }]
                    },
                    "routing": {
                        "selected_model": effective_model.alias,
                        "stoploss_triggered": False
                    }
                }
                
            else:
                raise ValueError(f"Model type {effective_model.model_type} not supported for ask operation")
                
        except Exception as e:
            logger.error(f"AI call failed: {e}")
            raise
    
    async def draft_with_model_selection(
        self,
        outline: List[str],
        board_id: UUID,
        user_id: int,
        max_out_tokens: int = 1500,
        model: Optional[str] = None,
        budget_wtu: Optional[int] = None,
        confidence_target: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        모델 선택을 지원하는 초안 작성
        
        Args:
            outline: 초안 개요
            board_id: 보드 ID
            user_id: 사용자 ID
            max_out_tokens: 최대 출력 토큰 수
            model: 요청된 모델 (별칭)
            budget_wtu: 예산 WTU 제한
            confidence_target: 품질 목표
            
        Returns:
            초안 결과와 사용량 정보
        """
        
        # 1. 유효한 모델 결정 (간소화된 버전)
        if model:
            # 요청된 모델이 있으면 해당 모델 사용
            effective_model = await model_catalog_service.get_model_by_alias(model)
        else:
            # 기본 모델 사용 (첫 번째 활성 LLM 모델)
            active_models = await model_catalog_service.get_active_models("llm")
            effective_model = active_models[0] if active_models else None
        
        if not effective_model:
            raise ValueError("No valid model available for this request")
        
        # 2. 입력 토큰 계산
        outline_text = "\n".join([f"- {item}" for item in outline])
        input_tokens = count_tokens(f"Create a draft based on this outline:\n{outline_text}", effective_model.model_name)
        estimated_output_tokens = min(max_out_tokens, 2000)  # 보수적 추정
        
        # 간단한 WTU 계산
        estimated_wtu = int(
            input_tokens * (effective_model.weight_input or 1.0) + 
            estimated_output_tokens * (effective_model.weight_output or 4.0)
        )
        
        # 3. 예산 확인 (간소화된 버전)
        if budget_wtu and estimated_wtu > budget_wtu:
            raise ValueError(f"Budget exceeded: estimated {estimated_wtu} WTU would exceed budget of {budget_wtu}")
        
        # 4. 초안 생성 (Mock 구현)
        try:
            # Mock 초안 생성
            draft = f"""# 초안 문서

**선택된 모델**: {effective_model.alias} ({effective_model.provider})
**예상 WTU**: {estimated_wtu}

## 개요
{outline_text}

## 상세 내용

이것은 Model Picker v1 테스트용 Mock 초안입니다.
실제 구현에서는 여기서 AI 모델을 사용하여 주어진 개요를 바탕으로 상세한 초안을 생성합니다.

각 개요 항목에 대해 체계적이고 논리적인 내용을 작성하며,
사용자가 요청한 형식과 길이에 맞춰 결과를 제공합니다.

---
*Generated by {effective_model.alias}*
"""
            
            actual_output_tokens = count_tokens(draft, effective_model.model_name)
            
            # 실제 WTU 재계산
            actual_wtu = int(
                input_tokens * (effective_model.weight_input or 1.0) + 
                actual_output_tokens * (effective_model.weight_output or 4.0)
            )
            
            # 6. 응답 구성
            return {
                "draft_md": draft,
                "outline_used": outline,
                "usage": {
                    "in": input_tokens,
                    "cached_in": 0,
                    "out": actual_output_tokens,
                    "embed": 0,
                    "wtu": actual_wtu,
                    "per_model": [{
                        "model": effective_model.alias,
                        "wtu": actual_wtu,
                        "in": input_tokens,
                        "out": actual_output_tokens
                    }]
                },
                "routing": {
                    "selected_model": effective_model.alias,
                    "stoploss_triggered": False
                }
            }
            
        except Exception as e:
            logger.error(f"Draft generation failed: {e}")
            raise


# 전역 서비스 인스턴스
with_ai_service = WithAIService()
