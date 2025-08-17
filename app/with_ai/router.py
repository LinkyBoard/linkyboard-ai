"""
With AI Router - 모델 선택 지원 AI 질의 엔드포인트
"""

from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.logging import get_logger
from app.with_ai.service import with_ai_service
from app.with_ai.schemas import (
    AskRequest,
    AskResponse,
    DraftRequest,
    DraftResponse,
    ModelBudgetRequest,
    ModelBudgetResponse
)

logger = get_logger(__name__)

# Router 인스턴스 생성
router = APIRouter(
    prefix="/with-ai",
    tags=["with-ai"],
    responses={
        400: {"description": "Bad Request"},
        403: {"description": "Budget Exceeded"},
        404: {"description": "Not found"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)


@router.post("/ask", response_model=AskResponse)
async def ask_with_model(
    request: AskRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    모델 선택을 지원하는 AI 질의
    
    사용자가 지정한 모델이나 보드/사용자 정책에 따른 모델로 질의를 처리합니다.
    WTU 예산 및 정책 제한을 확인하여 안전하게 실행됩니다.
    """
    try:
        logger.info(f"AI ask request - user: {request.user_id}, board: {request.board_id}, model: {request.model}")
        
        result = await with_ai_service.ask_with_model_selection(
            query=request.query,
            board_id=request.board_id,
            user_id=request.user_id,
            k=request.k,
            max_out_tokens=request.max_out_tokens,
            model=request.model,
            budget_wtu=request.budget_wtu,
            confidence_target=request.confidence_target
        )
        
        return AskResponse(**result)
        
    except ValueError as e:
        logger.warning(f"Ask request validation failed: {str(e)}")
        if "budget" in str(e).lower() or "exceeded" in str(e).lower():
            raise HTTPException(status_code=403, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ask request failed: {str(e)}")
        raise HTTPException(status_code=500, detail="AI 질의 처리 중 오류가 발생했습니다.")


@router.post("/draft", response_model=DraftResponse)
async def draft_with_model(
    request: DraftRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    모델 선택을 지원하는 초안 작성
    
    사용자가 지정한 모델이나 보드/사용자 정책에 따른 모델로 초안을 작성합니다.
    WTU 예산 및 정책 제한을 확인하여 안전하게 실행됩니다.
    """
    try:
        logger.info(f"AI draft request - user: {request.user_id}, board: {request.board_id}, model: {request.model}")
        
        result = await with_ai_service.draft_with_model_selection(
            outline=request.outline,
            board_id=request.board_id,
            user_id=request.user_id,
            max_out_tokens=request.max_out_tokens,
            model=request.model,
            budget_wtu=request.budget_wtu,
            confidence_target=request.confidence_target
        )
        
        return DraftResponse(**result)
        
    except ValueError as e:
        logger.warning(f"Draft request validation failed: {str(e)}")
        if "budget" in str(e).lower() or "exceeded" in str(e).lower():
            raise HTTPException(status_code=403, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Draft request failed: {str(e)}")
        raise HTTPException(status_code=500, detail="초안 작성 중 오류가 발생했습니다.")


@router.post("/budget/estimate", response_model=ModelBudgetResponse)
async def estimate_budget(
    request: ModelBudgetRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    모델별 예상 WTU 비용 계산
    
    입력된 텍스트와 예상 출력 토큰에 대해 각 모델별 WTU 비용을 계산합니다.
    """
    try:
        from app.metrics.model_catalog_service import model_catalog_service
        from app.metrics import count_tokens
        
        # LLM 모델만 조회 (임베딩 모델 제외)
        available_models = await model_catalog_service.get_active_models(
            model_type="llm",
            session=session
        )
        
        estimates = []
        for model in available_models:
            # 토큰 수 계산
            input_tokens = count_tokens(request.input_text, model.model_name)
            
            # 간단한 WTU 계산 (weight 정보 활용)
            estimated_wtu = int(
                input_tokens * (model.weight_input or 1.0) + 
                request.estimated_output_tokens * (model.weight_output or 4.0)
            )
            
            estimates.append({
                "model_alias": model.alias,
                "model_name": model.model_name,
                "input_tokens": input_tokens,
                "estimated_output_tokens": request.estimated_output_tokens,
                "estimated_wtu": estimated_wtu,
                "provider": model.provider
            })
        
        # WTU 순으로 정렬
        estimates.sort(key=lambda x: x["estimated_wtu"])
        
        return ModelBudgetResponse(
            estimates=estimates,
            total_available_models=len(estimates)
        )
        
    except Exception as e:
        logger.error(f"Budget estimation failed: {str(e)}")
        raise HTTPException(status_code=500, detail="예산 계산 중 오류가 발생했습니다.")


@router.get("/models/available")
async def get_available_models(
    board_id: UUID,
    user_id: int,
    model_type: str = "llm",  # 기본값을 LLM으로 고정, 임베딩 모델은 사용자 선택에서 제외
    session: AsyncSession = Depends(get_db)
):
    """
    사용 가능한 모델 목록 조회 (LLM만, 임베딩 모델 제외)
    
    보드/사용자 정책에 따라 사용 가능한 모델 목록을 반환합니다.
    """
    try:
        from app.metrics.model_catalog_service import model_catalog_service
        
        # LLM 모델만 조회 (임베딩 모델 제외)
        models = await model_catalog_service.get_active_models(
            model_type="llm",
            session=session
        )
        
        return {
            "models": [
                {
                    "alias": model.alias,
                    "model_name": model.model_name,
                    "provider": model.provider,
                    "description": f"{model.provider} {model.model_name}",
                    "is_default": False  # 실제로는 정책에서 결정
                }
                for model in models
            ],
            "total_count": len(models)
        }
        
    except Exception as e:
        logger.error(f"Available models query failed: {str(e)}")
        raise HTTPException(status_code=500, detail="모델 목록 조회 중 오류가 발생했습니다.")
