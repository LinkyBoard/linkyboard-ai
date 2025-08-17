"""
보드 모델 정책 API 라우터
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.metrics.model_policy_service import model_policy_service
from app.metrics.model_catalog_service import model_catalog_service
from .schemas import (
    BoardModelPolicyResponse,
    BoardModelPolicyCreateRequest,
    BoardModelPolicyUpdateRequest,
    AvailableModelsResponse
)

router = APIRouter(prefix="/boards", tags=["boards", "model-policy"])


@router.get("/{board_id}/available-models", response_model=AvailableModelsResponse)
async def get_available_models(
    board_id: UUID,
    model_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """보드에서 사용 가능한 모델 목록 조회"""
    try:
        # 보드 정책 확인
        board_policy = await model_policy_service.get_board_policy(board_id, db)
        
        # 활성 모델 목록 조회
        all_models = await model_catalog_service.get_active_models(model_type, db)
        
        # 허용된 모델만 필터링
        if board_policy and board_policy.allowed_model_ids:
            allowed_models = [m for m in all_models if m.id in board_policy.allowed_model_ids]
        else:
            allowed_models = all_models
        
        models_data = []
        for model in allowed_models:
            # WTU 가중치 조회
            llm_model = model.model_name if model.model_type == "llm" else None
            embed_model = model.model_name if model.model_type == "embedding" else None
            weights = await model_catalog_service.get_wtu_weights(llm_model, embed_model, db)
            
            estimated_wtu_per_1k = {}
            if model.model_type == "llm":
                estimated_wtu_per_1k = {
                    "input": weights['w_in'] * 1000,
                    "output": weights['w_out'] * 1000
                }
            elif model.model_type == "embedding":
                estimated_wtu_per_1k = {
                    "embedding": weights['w_embed'] * 1000
                }
            
            models_data.append({
                "id": model.id,
                "alias": model.alias,
                "model_type": model.model_type,
                "estimated_wtu_per_1k": estimated_wtu_per_1k
            })
        
        return AvailableModelsResponse(
            board_id=board_id,
            models=models_data,
            default_model_id=board_policy.default_model_id if board_policy else None
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get available models: {str(e)}"
        )


@router.get("/{board_id}/model-policy", response_model=BoardModelPolicyResponse)
async def get_board_policy(
    board_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """보드 모델 정책 조회"""
    try:
        policy = await model_policy_service.get_board_policy(board_id, db)
        
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No model policy found for board {board_id}"
            )
        
        return BoardModelPolicyResponse(
            board_id=policy.board_id,
            default_model_id=policy.default_model_id,
            allowed_model_ids=policy.allowed_model_ids or [],
            budget_wtu=policy.budget_wtu,
            confidence_target=policy.confidence_target,
            created_at=policy.created_at,
            updated_at=policy.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get board policy: {str(e)}"
        )


@router.post("/{board_id}/model-policy", response_model=BoardModelPolicyResponse)
async def create_board_policy(
    board_id: UUID,
    request: BoardModelPolicyCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """보드 모델 정책 생성"""
    try:
        # 모델 유효성 검사
        if request.default_model_id:
            if not await model_policy_service.validate_model_selection(request.default_model_id, session=db):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid default model ID: {request.default_model_id}"
                )
        
        if request.allowed_model_ids:
            for model_id in request.allowed_model_ids:
                if not await model_policy_service.validate_model_selection(model_id, session=db):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid allowed model ID: {model_id}"
                    )
        
        # 정책 생성
        policy = await model_policy_service.create_or_update_board_policy(
            board_id=board_id,
            default_model_id=request.default_model_id,
            allowed_model_ids=request.allowed_model_ids,
            budget_wtu=request.budget_wtu,
            confidence_target=request.confidence_target,
            session=db
        )
        
        return BoardModelPolicyResponse(
            board_id=policy.board_id,
            default_model_id=policy.default_model_id,
            allowed_model_ids=policy.allowed_model_ids or [],
            budget_wtu=policy.budget_wtu,
            confidence_target=policy.confidence_target,
            created_at=policy.created_at,
            updated_at=policy.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create board policy: {str(e)}"
        )


@router.put("/{board_id}/model-policy", response_model=BoardModelPolicyResponse)
async def update_board_policy(
    board_id: UUID,
    request: BoardModelPolicyUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """보드 모델 정책 업데이트"""
    try:
        # 모델 유효성 검사
        if request.default_model_id:
            if not await model_policy_service.validate_model_selection(request.default_model_id, session=db):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid default model ID: {request.default_model_id}"
                )
        
        if request.allowed_model_ids:
            for model_id in request.allowed_model_ids:
                if not await model_policy_service.validate_model_selection(model_id, session=db):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid allowed model ID: {model_id}"
                    )
        
        # 정책 업데이트
        policy = await model_policy_service.create_or_update_board_policy(
            board_id=board_id,
            default_model_id=request.default_model_id,
            allowed_model_ids=request.allowed_model_ids,
            budget_wtu=request.budget_wtu,
            confidence_target=request.confidence_target,
            session=db
        )
        
        return BoardModelPolicyResponse(
            board_id=policy.board_id,
            default_model_id=policy.default_model_id,
            allowed_model_ids=policy.allowed_model_ids or [],
            budget_wtu=policy.budget_wtu,
            confidence_target=policy.confidence_target,
            created_at=policy.created_at,
            updated_at=policy.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update board policy: {str(e)}"
        )
