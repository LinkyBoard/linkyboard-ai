"""
사용자별 토큰 쿼터 관리 서비스

토큰 쿼터 조회, 소비, 충전 기능을 제공합니다.
"""

import logging
from datetime import date, datetime
from typing import Optional, Dict, Any, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal
from app.core.models import UserTokenQuota, TokenPurchase, User

logger = logging.getLogger(__name__)


class InsufficientTokensError(Exception):
    """토큰 부족 에러"""
    def __init__(self, required: int, available: int):
        self.required = required
        self.available = available
        super().__init__(f"토큰 부족: 필요={required}, 사용가능={available}")


async def get_or_create_user_quota(
    user_id: int,
    plan_month: Optional[date] = None,
    session: Optional[AsyncSession] = None
) -> UserTokenQuota:
    """
    사용자의 토큰 쿼터를 조회하거나 생성
    
    Args:
        user_id: 사용자 ID
        plan_month: 조회할 월 (기본값: 현재 월)
        session: DB 세션
        
    Returns:
        UserTokenQuota 객체
    """
    if plan_month is None:
        plan_month = date.today().replace(day=1)
    
    close_session = False
    if session is None:
        session = AsyncSessionLocal()
        close_session = True
    
    try:
        # 기존 쿼터 조회
        stmt = select(UserTokenQuota).where(
            UserTokenQuota.user_id == user_id,
            UserTokenQuota.plan_month == plan_month
        )
        result = await session.execute(stmt)
        quota = result.scalar_one_or_none()
        
        if quota is None:
            # 새 쿼터 생성 (기본 할당량: 10,000 토큰)
            quota = UserTokenQuota(
                user_id=user_id,
                plan_month=plan_month,
                allocated_quota=10000,
                used_tokens=0,
                remaining_tokens=10000,
                total_purchased=0
            )
            session.add(quota)
            await session.commit()
            await session.refresh(quota)
            
            logger.info(f"Created new token quota for user {user_id}, month {plan_month}")
        
        return quota
        
    except IntegrityError as e:
        await session.rollback()
        logger.error(f"Failed to create quota: {e}")
        raise
    finally:
        if close_session:
            await session.aclose()


async def check_token_availability(
    user_id: int,
    required_tokens: int,
    plan_month: Optional[date] = None,
    session: Optional[AsyncSession] = None
) -> bool:
    """
    토큰 사용 가능 여부 확인
    
    Args:
        user_id: 사용자 ID
        required_tokens: 필요한 토큰 수
        plan_month: 조회할 월
        session: DB 세션
        
    Returns:
        토큰 사용 가능 여부
    """
    quota = await get_or_create_user_quota(user_id, plan_month, session)
    return quota.can_consume(required_tokens)


async def consume_tokens(
    user_id: int,
    token_amount: int,
    plan_month: Optional[date] = None,
    session: Optional[AsyncSession] = None
) -> UserTokenQuota:
    """
    토큰 소비
    
    Args:
        user_id: 사용자 ID
        token_amount: 소비할 토큰 수
        plan_month: 해당 월
        session: DB 세션
        
    Returns:
        업데이트된 UserTokenQuota 객체
        
    Raises:
        InsufficientTokensError: 토큰 부족 시
    """
    if plan_month is None:
        plan_month = date.today().replace(day=1)
    
    close_session = False
    if session is None:
        session = AsyncSessionLocal()
        close_session = True
    
    try:
        quota = await get_or_create_user_quota(user_id, plan_month, session)
        
        if not quota.consume_tokens(token_amount):
            raise InsufficientTokensError(token_amount, quota.remaining_tokens)
        
        await session.commit()
        await session.refresh(quota)
        
        logger.info(f"Consumed {token_amount} tokens for user {user_id}. Remaining: {quota.remaining_tokens}")
        
        return quota
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to consume tokens: {e}")
        raise
    finally:
        if close_session:
            await session.aclose()


async def purchase_tokens(
    user_id: int,
    token_amount: int,
    purchase_type: str = "purchase",
    payment_method: Optional[str] = None,
    payment_amount: Optional[float] = None,
    currency: str = "KRW",
    transaction_id: Optional[str] = None,
    plan_month: Optional[date] = None,
    session: Optional[AsyncSession] = None
) -> TokenPurchase:
    """
    토큰 구매/충전
    
    Args:
        user_id: 사용자 ID
        token_amount: 구매할 토큰 수
        purchase_type: 구매 유형 (purchase, bonus, refund)
        payment_method: 결제 수단
        payment_amount: 결제 금액
        currency: 통화
        transaction_id: 거래 ID
        plan_month: 해당 월
        session: DB 세션
        
    Returns:
        생성된 TokenPurchase 객체
    """
    if plan_month is None:
        plan_month = date.today().replace(day=1)
    
    close_session = False
    if session is None:
        session = AsyncSessionLocal()
        close_session = True
    
    try:
        # 쿼터 조회/생성
        quota = await get_or_create_user_quota(user_id, plan_month, session)
        
        # 구매 기록 생성
        purchase = TokenPurchase(
            user_id=user_id,
            plan_month=plan_month,
            token_amount=token_amount,
            purchase_type=purchase_type,
            payment_method=payment_method,
            payment_amount=payment_amount,
            currency=currency,
            transaction_id=transaction_id,
            status="completed",
            processed_at=datetime.now()
        )
        session.add(purchase)
        
        # 쿼터 업데이트
        quota.add_quota(token_amount)
        
        await session.commit()
        await session.refresh(purchase)
        await session.refresh(quota)
        
        logger.info(f"Purchased {token_amount} tokens for user {user_id}. New quota: {quota.allocated_quota}")
        
        return purchase
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to purchase tokens: {e}")
        raise
    finally:
        if close_session:
            await session.aclose()


async def get_user_quota_info(
    user_id: int,
    plan_month: Optional[date] = None,
    session: Optional[AsyncSession] = None
) -> Dict[str, Any]:
    """
    사용자 토큰 쿼터 정보 조회
    
    Args:
        user_id: 사용자 ID
        plan_month: 조회할 월
        session: DB 세션
        
    Returns:
        토큰 쿼터 정보 딕셔너리
    """
    quota = await get_or_create_user_quota(user_id, plan_month, session)
    
    return {
        "user_id": quota.user_id,
        "plan_month": quota.plan_month,
        "allocated_quota": quota.allocated_quota,
        "used_tokens": quota.used_tokens,
        "remaining_tokens": quota.remaining_tokens,
        "total_purchased": quota.total_purchased,
        "usage_percentage": quota.usage_percentage,
        "is_quota_exceeded": quota.is_quota_exceeded,
        "created_at": quota.created_at,
        "updated_at": quota.updated_at
    }


async def get_user_purchase_history(
    user_id: int,
    plan_month: Optional[date] = None,
    limit: int = 50,
    session: Optional[AsyncSession] = None
) -> List[TokenPurchase]:
    """
    사용자 토큰 구매 이력 조회
    
    Args:
        user_id: 사용자 ID
        plan_month: 조회할 월 (None이면 전체)
        limit: 조회 개수 제한
        session: DB 세션
        
    Returns:
        TokenPurchase 객체 리스트
    """
    close_session = False
    if session is None:
        session = AsyncSessionLocal()
        close_session = True
    
    try:
        stmt = select(TokenPurchase).where(TokenPurchase.user_id == user_id)
        
        if plan_month:
            stmt = stmt.where(TokenPurchase.plan_month == plan_month)
        
        stmt = stmt.order_by(TokenPurchase.created_at.desc()).limit(limit)
        
        result = await session.execute(stmt)
        purchases = result.scalars().all()
        
        logger.debug(f"Retrieved {len(purchases)} purchase records for user {user_id}")
        
        return purchases
        
    finally:
        if close_session:
            await session.aclose()


async def reset_monthly_quota(
    user_id: int,
    new_quota: int = 10000,
    plan_month: Optional[date] = None,
    session: Optional[AsyncSession] = None
) -> UserTokenQuota:
    """
    월별 쿼터 초기화 (월 초 실행용)
    
    Args:
        user_id: 사용자 ID
        new_quota: 새로운 기본 할당량
        plan_month: 해당 월
        session: DB 세션
        
    Returns:
        초기화된 UserTokenQuota 객체
    """
    if plan_month is None:
        plan_month = date.today().replace(day=1)
    
    close_session = False
    if session is None:
        session = AsyncSessionLocal()
        close_session = True
    
    try:
        # 기존 쿼터 조회
        stmt = select(UserTokenQuota).where(
            UserTokenQuota.user_id == user_id,
            UserTokenQuota.plan_month == plan_month
        )
        result = await session.execute(stmt)
        quota = result.scalar_one_or_none()
        
        if quota:
            # 기존 쿼터 업데이트
            quota.allocated_quota = new_quota
            quota.used_tokens = 0
            quota.remaining_tokens = new_quota
            quota.total_purchased = 0
        else:
            # 새 쿼터 생성
            quota = UserTokenQuota(
                user_id=user_id,
                plan_month=plan_month,
                allocated_quota=new_quota,
                used_tokens=0,
                remaining_tokens=new_quota,
                total_purchased=0
            )
            session.add(quota)
        
        await session.commit()
        await session.refresh(quota)
        
        logger.info(f"Reset quota for user {user_id}, month {plan_month}: {new_quota} tokens")
        
        return quota
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to reset quota: {e}")
        raise
    finally:
        if close_session:
            await session.aclose()