"""
사용자 토큰 쿼터 관리 API 라우터
"""

import logging
from datetime import date, datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.metrics.token_quota_service import (
    get_user_quota_info,
    get_user_purchase_history,
    purchase_tokens,
    InsufficientTokensError
)
from app.user_quota.schemas import (
    TokenQuotaResponse,
    TokenPurchaseRequest,
    TokenPurchaseResponse,
    TokenUsageHistoryResponse
)
# Payment service will be handled by Spring Boot server

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/user-quota", tags=["User Token Quota"])


@router.get("/quota", response_model=TokenQuotaResponse)
async def get_user_quota(
    user_id: int = Header(..., alias="x-user-id"),
    plan_month: Optional[str] = Query(None, description="조회할 월 (YYYY-MM-01 형식)"),
    session: AsyncSession = Depends(get_async_session)
):
    """
    사용자의 토큰 쿼터 정보 조회
    
    - 할당된 총 토큰 수
    - 사용된 토큰 수
    - 남은 토큰 수
    - 사용률 등
    """
    try:
        # 날짜 파싱
        target_month = None
        if plan_month:
            try:
                target_month = datetime.strptime(plan_month, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="잘못된 날짜 형식입니다. YYYY-MM-DD 형식을 사용하세요."
                )
        
        quota_info = await get_user_quota_info(user_id, target_month, session)
        
        return TokenQuotaResponse(
            user_id=quota_info["user_id"],
            plan_month=quota_info["plan_month"],
            allocated_quota=quota_info["allocated_quota"],
            used_tokens=quota_info["used_tokens"],
            remaining_tokens=quota_info["remaining_tokens"],
            total_purchased=quota_info["total_purchased"],
            usage_percentage=quota_info["usage_percentage"],
            is_quota_exceeded=quota_info["is_quota_exceeded"],
            created_at=quota_info["created_at"],
            updated_at=quota_info["updated_at"]
        )
        
    except Exception as e:
        logger.error(f"Failed to get user quota: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="토큰 쿼터 정보를 조회할 수 없습니다."
        )


@router.get("/usage-history", response_model=List[TokenUsageHistoryResponse])
async def get_usage_history(
    user_id: int = Header(..., alias="x-user-id"),
    plan_month: Optional[str] = Query(None, description="조회할 월 (YYYY-MM-01 형식)"),
    limit: int = Query(50, description="조회할 기록 수", le=100),
    session: AsyncSession = Depends(get_async_session)
):
    """
    사용자의 토큰 사용 이력 조회
    """
    try:
        # 날짜 파싱
        target_month = None
        if plan_month:
            try:
                target_month = datetime.strptime(plan_month, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="잘못된 날짜 형식입니다. YYYY-MM-DD 형식을 사용하세요."
                )
        
        purchases = await get_user_purchase_history(user_id, target_month, limit, session)
        
        return [
            TokenUsageHistoryResponse(
                id=purchase.id,
                user_id=purchase.user_id,
                plan_month=purchase.plan_month,
                token_amount=purchase.token_amount,
                purchase_type=purchase.purchase_type,
                payment_method=purchase.payment_method,
                payment_amount=purchase.payment_amount,
                currency=purchase.currency,
                status=purchase.status,
                transaction_id=purchase.transaction_id,
                created_at=purchase.created_at,
                processed_at=purchase.processed_at
            )
            for purchase in purchases
        ]
        
    except Exception as e:
        logger.error(f"Failed to get usage history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용 이력을 조회할 수 없습니다."
        )


@router.post("/purchase", response_model=TokenPurchaseResponse)
async def purchase_user_tokens(
    request: TokenPurchaseRequest,
    user_id: int = Header(..., alias="x-user-id"),
    session: AsyncSession = Depends(get_async_session)
):
    """
    토큰 구매/충전
    """
    try:
        # 날짜 파싱
        target_month = None
        if request.plan_month:
            target_month = request.plan_month
        
        purchase = await purchase_tokens(
            user_id=user_id,
            token_amount=request.token_amount,
            purchase_type=request.purchase_type,
            payment_method=request.payment_method,
            payment_amount=request.payment_amount,
            currency=request.currency,
            transaction_id=request.transaction_id,
            plan_month=target_month,
            session=session
        )
        
        logger.info(f"Token purchase successful: user_id={user_id}, amount={request.token_amount}")
        
        return TokenPurchaseResponse(
            id=purchase.id,
            user_id=purchase.user_id,
            plan_month=purchase.plan_month,
            token_amount=purchase.token_amount,
            purchase_type=purchase.purchase_type,
            payment_method=purchase.payment_method,
            payment_amount=purchase.payment_amount,
            currency=purchase.currency,
            status=purchase.status,
            transaction_id=purchase.transaction_id,
            created_at=purchase.created_at,
            processed_at=purchase.processed_at
        )
        
    except Exception as e:
        logger.error(f"Token purchase failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"토큰 구매에 실패했습니다: {str(e)}"
        )


@router.get("/quota/current", response_model=TokenQuotaResponse)
async def get_current_quota(
    user_id: int = Header(..., alias="x-user-id"),
    session: AsyncSession = Depends(get_async_session)
):
    """
    현재 월의 토큰 쿼터 정보 조회 (간편 API)
    """
    return await get_user_quota(user_id=user_id, session=session)


@router.get("/quota/check/{required_tokens}")
async def check_quota_availability(
    required_tokens: int,
    user_id: int = Header(..., alias="x-user-id"),
    session: AsyncSession = Depends(get_async_session)
):
    """
    특정 토큰 수 사용 가능 여부 확인
    """
    try:
        from app.metrics.token_quota_service import check_token_availability
        
        available = await check_token_availability(user_id, required_tokens, session=session)
        quota_info = await get_user_quota_info(user_id, session=session)
        
        return {
            "user_id": user_id,
            "required_tokens": required_tokens,
            "available": available,
            "remaining_tokens": quota_info["remaining_tokens"],
            "total_quota": quota_info["allocated_quota"]
        }
        
    except Exception as e:
        logger.error(f"Failed to check quota availability: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="토큰 사용 가능 여부를 확인할 수 없습니다."
        )


# Payment endpoints moved to Spring Boot server
# Only quota management remains in AI service

@router.post("/add-tokens")
async def add_tokens_manually(
    request: dict,
    user_id: int = Header(..., alias="x-user-id"),
    session: AsyncSession = Depends(get_async_session)
):
    """
    수동 토큰 추가 (Spring Boot 서버에서 호출용)
    
    Request body:
    {
        "token_amount": 1000,
        "purchase_type": "purchase",
        "transaction_id": "tx_123"
    }
    """
    try:
        token_amount = request.get("token_amount")
        purchase_type = request.get("purchase_type", "purchase")
        transaction_id = request.get("transaction_id")
        
        if not token_amount or token_amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효한 토큰 수량이 필요합니다."
            )
        
        purchase = await purchase_tokens(
            user_id=user_id,
            token_amount=token_amount,
            purchase_type=purchase_type,
            transaction_id=transaction_id,
            session=session
        )
        
        return {
            "success": True,
            "purchase_id": purchase.id,
            "user_id": user_id,
            "token_amount": token_amount,
            "transaction_id": transaction_id,
            "created_at": purchase.created_at.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Token addition failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"토큰 추가에 실패했습니다: {str(e)}"
        )