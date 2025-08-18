"""
Board AI Router - 선택된 아이템 기반 AI 작업 엔드포인트
"""

from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.logging import get_logger
from app.board_ai.service import board_ai_service
from app.board_ai.schemas import (
    AskWithItemsRequest,
    AskWithItemsResponse,
    DraftWithItemsRequest,
    DraftWithItemsResponse,
    CostEstimateRequest,
    CostEstimateResponse,
    AvailableModelsResponse
)

logger = get_logger(__name__)

# Router 인스턴스 생성
router = APIRouter(
    prefix="/board-ai",
    tags=["board-ai"],
    responses={
        400: {"description": "Bad Request"},
        404: {"description": "Not found"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)


@router.get("/models/available", response_model=AvailableModelsResponse)
async def get_available_models(
    session: AsyncSession = Depends(get_db)
):
    """
    사용 가능한 AI 모델 목록 조회
    
    현재 시스템에서 사용 가능한 모든 LLM 모델의 목록과 비용 정보를 반환합니다.
    사용자가 작업에 사용할 모델을 선택할 때 참고할 수 있습니다.
    """
    try:
        logger.info("Available models request")
        
        result = await board_ai_service.get_available_models()
        
        return AvailableModelsResponse(**result)
        
    except Exception as e:
        logger.error(f"Get available models failed: {str(e)}")
        raise HTTPException(status_code=500, detail="모델 목록 조회 중 오류가 발생했습니다.")


@router.post("/models/estimate-cost", response_model=CostEstimateResponse)
async def estimate_cost(
    request: CostEstimateRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    선택된 아이템 기반 작업 비용 추정
    
    사용자가 선택한 아이템들과 수행할 작업을 기반으로
    각 모델별 예상 비용(WTU)을 계산합니다.
    """
    try:
        logger.info(f"Cost estimate request - user: {request.user_id}, board: {request.board_id}, items: {len(request.selected_items)}")
        
        result = await board_ai_service.estimate_task_cost(
            selected_items=request.selected_items,
            task_description=request.task_description,
            board_id=request.board_id,
            user_id=request.user_id,
            estimated_output_tokens=request.estimated_output_tokens,
            session=session
        )
        
        return CostEstimateResponse(**result)
        
    except Exception as e:
        logger.error(f"Cost estimate failed: {str(e)}")
        raise HTTPException(status_code=500, detail="비용 추정 중 오류가 발생했습니다.")


@router.post("/ask-with-items", response_model=AskWithItemsResponse)
async def ask_with_items(
    request: AskWithItemsRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    선택된 아이템들을 기반으로 한 AI 질의
    
    사용자가 보드에서 선택한 아이템들의 내용을 바탕으로 AI 질의를 수행합니다.
    사용자가 지정한 모델로 질의를 처리하며, 실제 아이템 데이터를 활용합니다.
    """
    try:
        logger.info(f"AI ask-with-items request - user: {request.user_id}, board: {request.board_id}, items: {len(request.selected_items)}, model: {request.model_alias}")
        
        result = await board_ai_service.ask_with_selected_items(
            query=request.query,
            instruction=request.instruction,
            selected_items=request.selected_items,
            board_id=request.board_id,
            user_id=request.user_id,
            model_alias=request.model_alias,
            max_output_tokens=request.max_output_tokens,
            session=session
        )
        
        return AskWithItemsResponse(**result)
        
    except ValueError as e:
        logger.warning(f"Ask-with-items request validation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ask-with-items request failed: {str(e)}")
        raise HTTPException(status_code=500, detail="선택된 아이템 기반 AI 질의 처리 중 오류가 발생했습니다.")


@router.post("/draft-with-items", response_model=DraftWithItemsResponse)
async def draft_with_items(
    request: DraftWithItemsRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    선택된 아이템들을 기반으로 한 초안 작성
    
    사용자가 보드에서 선택한 아이템들의 내용을 바탕으로 초안을 작성합니다.
    콘텐츠 유형과 요구사항에 따라 맞춤형 초안을 생성합니다.
    """
    try:
        logger.info(f"AI draft-with-items request - user: {request.user_id}, board: {request.board_id}, items: {len(request.selected_items)}, model: {request.model_alias}")
        
        result = await board_ai_service.draft_with_selected_items(
            requirements=request.requirements,
            selected_items=request.selected_items,
            board_id=request.board_id,
            user_id=request.user_id,
            model_alias=request.model_alias,
            session=session
        )
        
        return DraftWithItemsResponse(**result)
        
    except ValueError as e:
        logger.warning(f"Draft-with-items request validation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Draft-with-items request failed: {str(e)}")
        raise HTTPException(status_code=500, detail="선택된 아이템 기반 초안 작성 중 오류가 발생했습니다.")