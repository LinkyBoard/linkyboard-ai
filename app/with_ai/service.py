"""
With AI 서비스 - 모델 선택 지원
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date

from app.metrics.model_policy_service import model_policy_service
from app.metrics.model_catalog_service import model_catalog_service
from app.metrics.usage_recorder_v2 import record_usage, get_board_total_monthly_wtu
from app.core.logging import get_logger
from app.ai.openai_service import openai_service
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
        
        # 1. 유효한 모델 결정
        effective_model = await model_policy_service.get_effective_model(
            requested_model=model,
            board_id=board_id,
            user_id=user_id,
            model_type="llm"
        )
        
        if not effective_model:
            raise ValueError("No valid model available for this request")
        
        # 2. 예상 WTU 계산
        input_tokens = count_tokens(query, effective_model.model_name)
        estimated_output_tokens = min(max_out_tokens, 1000)  # 보수적 추정
        
        estimated_wtu = await model_policy_service.estimate_wtu_cost(
            model=effective_model,
            estimated_input_tokens=input_tokens,
            estimated_output_tokens=estimated_output_tokens
        )
        
        # 3. 예산 확인
        current_month = date.today().replace(day=1)
        current_month_wtu = await get_board_total_monthly_wtu(board_id, current_month)
        
        if budget_wtu:
            if current_month_wtu + estimated_wtu > budget_wtu:
                raise ValueError(f"Budget exceeded: estimated {estimated_wtu} WTU would exceed budget of {budget_wtu}")
        
        # 보드 정책의 예산도 확인
        if not await model_policy_service.check_budget_limit(board_id, estimated_wtu, current_month_wtu):
            raise ValueError("Board budget limit would be exceeded")
        
        # 4. AI 호출 수행
        try:
            # OpenAI 서비스 호출 (기존 구현 활용)
            if effective_model.model_type == "llm":
                # 모델명을 환경변수에 임시 설정 (실제로는 openai_service를 확장해야 함)
                original_model = openai_service.client._default_model if hasattr(openai_service.client, '_default_model') else None
                
                # 간단한 질의-응답 구현 (실제로는 더 복잡한 RAG 구현)
                system_prompt = f"""당신은 도움이 되는 AI 어시스턴트입니다. 
사용자의 질문에 대해 정확하고 유용한 답변을 제공해주세요.
최대 {max_out_tokens} 토큰 내에서 답변하세요."""
                
                response = await openai_service.client.chat.completions.create(
                    model=effective_model.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query}
                    ],
                    max_tokens=max_out_tokens,
                    temperature=0.7
                )
                
                answer = response.choices[0].message.content
                actual_output_tokens = count_tokens(answer, effective_model.model_name)
                
                # 5. 실제 사용량 기록
                usage_record = await record_usage(
                    user_id=user_id,
                    in_tokens=input_tokens,
                    out_tokens=actual_output_tokens,
                    llm_model=effective_model.model_name,
                    selected_model_id=effective_model.id,
                    board_id=board_id
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
                        "wtu": usage_record.wtu,
                        "per_model": [{
                            "model": effective_model.alias,
                            "wtu": usage_record.wtu,
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
        
        # 1. 유효한 모델 결정
        effective_model = await model_policy_service.get_effective_model(
            requested_model=model,
            board_id=board_id,
            user_id=user_id,
            model_type="llm"
        )
        
        if not effective_model:
            raise ValueError("No valid model available for this request")
        
        # 2. 입력 토큰 계산
        outline_text = "\n".join([f"- {item}" for item in outline])
        input_tokens = count_tokens(f"Create a draft based on this outline:\n{outline_text}", effective_model.model_name)
        estimated_output_tokens = min(max_out_tokens, 2000)  # 보수적 추정
        
        estimated_wtu = await model_policy_service.estimate_wtu_cost(
            model=effective_model,
            estimated_input_tokens=input_tokens,
            estimated_output_tokens=estimated_output_tokens
        )
        
        # 3. 예산 확인
        current_month = date.today().replace(day=1)
        current_month_wtu = await get_board_total_monthly_wtu(board_id, current_month)
        
        if budget_wtu:
            if current_month_wtu + estimated_wtu > budget_wtu:
                raise ValueError(f"Budget exceeded: estimated {estimated_wtu} WTU would exceed budget of {budget_wtu}")
        
        if not await model_policy_service.check_budget_limit(board_id, estimated_wtu, current_month_wtu):
            raise ValueError("Board budget limit would be exceeded")
        
        # 4. AI 호출 수행
        try:
            system_prompt = f"""당신은 전문적인 문서 작성 어시스턴트입니다.
주어진 개요를 바탕으로 체계적이고 상세한 초안을 작성해주세요.
마크다운 형식으로 작성하고, 최대 {max_out_tokens} 토큰 내에서 완성하세요."""
            
            user_prompt = f"""다음 개요를 바탕으로 초안을 작성해주세요:

{outline_text}

각 항목을 자세히 설명하고, 논리적인 흐름으로 구성해주세요."""
            
            response = await openai_service.client.chat.completions.create(
                model=effective_model.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_out_tokens,
                temperature=0.3
            )
            
            draft = response.choices[0].message.content
            actual_output_tokens = count_tokens(draft, effective_model.model_name)
            
            # 5. 실제 사용량 기록
            usage_record = await record_usage(
                user_id=user_id,
                in_tokens=input_tokens,
                out_tokens=actual_output_tokens,
                llm_model=effective_model.model_name,
                selected_model_id=effective_model.id,
                board_id=board_id
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
                    "wtu": usage_record.wtu,
                    "per_model": [{
                        "model": effective_model.alias,
                        "wtu": usage_record.wtu,
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
