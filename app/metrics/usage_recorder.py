"""
사용량 기록 및 조회 서비스

WTU 사용량을 데이터베이스에 기록하고 조회하는 기능을 제공합니다.
"""

import logging
from datetime import date, datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.models import UsageMeter
from .wtu_calculator import calculate_wtu

logger = logging.getLogger(__name__)


async def record_usage(
    user_id: int,
    embed_tokens: int = 0,
    run_id: Optional[UUID] = None,
    in_tokens: int = 0,
    cached_in_tokens: int = 0,
    out_tokens: int = 0,
    llm_model: Optional[str] = None,
    embedding_model: Optional[str] = None,
    plan_month: Optional[date] = None,
    session: Optional[AsyncSession] = None
) -> UsageMeter:
    """
    사용량을 usage_meter 테이블에 기록 (모델 정보 포함)
    
    Args:
        user_id: 사용자 ID
        embed_tokens: 임베딩 토큰 수
        run_id: 실행 ID (선택사항)
        in_tokens: 입력 토큰 수
        cached_in_tokens: 캐시된 입력 토큰 수
        out_tokens: 출력 토큰 수
        llm_model: 사용된 LLM 모델명
        embedding_model: 사용된 임베딩 모델명
        plan_month: 계획 월 (기본값: 현재 월)
        session: DB 세션 (없으면 새로 생성)
        
    Returns:
        생성된 UsageMeter 레코드
    """
    if plan_month is None:
        # 현재 월의 첫째 날로 설정
        now = datetime.now()
        plan_month = date(now.year, now.month, 1)
    
    # WTU 및 비용 계산
    wtu, estimated_cost = await calculate_wtu(
        in_tokens=in_tokens,
        cached_in_tokens=cached_in_tokens,
        out_tokens=out_tokens,
        embed_tokens=embed_tokens,
        llm_model=llm_model,
        embedding_model=embedding_model,
        session=session
    )
    
    # 세션이 없으면 새로 생성
    close_session = False
    if session is None:
        session = await get_db().__anext__()
        close_session = True
    
    try:
        # 같은 사용자, 같은 월, 같은 모델 조합에 기존 레코드가 있는지 확인
        stmt = select(UsageMeter).where(
            UsageMeter.user_id == user_id,
            UsageMeter.plan_month == plan_month,
            UsageMeter.run_id == run_id,
            UsageMeter.llm_model == llm_model,
            UsageMeter.embedding_model == embedding_model
        )
        result = await session.execute(stmt)
        existing_record = result.scalar_one_or_none()
        
        if existing_record:
            # 기존 레코드 업데이트 (누적)
            existing_record.in_tokens += in_tokens
            existing_record.cached_in_tokens += cached_in_tokens
            existing_record.out_tokens += out_tokens
            existing_record.embed_tokens += embed_tokens
            
            # WTU 재계산
            new_wtu, new_cost = await calculate_wtu(
                in_tokens=existing_record.in_tokens,
                cached_in_tokens=existing_record.cached_in_tokens,
                out_tokens=existing_record.out_tokens,
                embed_tokens=existing_record.embed_tokens,
                llm_model=llm_model,
                embedding_model=embedding_model,
                session=session
            )
            existing_record.wtu = new_wtu
            existing_record.estimated_cost_usd = new_cost
            
            usage_record = existing_record
            logger.info(f"Updated existing usage record for user {user_id}, month {plan_month}")
        else:
            # 새 레코드 생성
            usage_record = UsageMeter(
                user_id=user_id,
                run_id=run_id,
                llm_model=llm_model,
                embedding_model=embedding_model,
                in_tokens=in_tokens,
                cached_in_tokens=cached_in_tokens,
                out_tokens=out_tokens,
                embed_tokens=embed_tokens,
                wtu=wtu,
                estimated_cost_usd=estimated_cost,
                plan_month=plan_month
            )
            session.add(usage_record)
            logger.info(f"Created new usage record for user {user_id}, month {plan_month}")
        
        await session.commit()
        await session.refresh(usage_record)
        
        logger.info(
            f"WTU recorded - User: {user_id}, Models: {llm_model}/{embedding_model}, "
            f"Embed tokens: {embed_tokens}, WTU: {usage_record.wtu}, "
            f"Cost: ${usage_record.estimated_cost_usd:.4f}, Month: {plan_month}"
        )
        
        return usage_record
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to record usage: {e}")
        raise
    finally:
        if close_session:
            await session.close()


async def record_embedding_usage(
    user_id: int,
    embed_tokens: int,
    embedding_model: str = "text-embedding-3-small",
    run_id: Optional[UUID] = None,
    session: Optional[AsyncSession] = None
) -> UsageMeter:
    """
    임베딩 전용 사용량 기록 (편의 함수)
    
    Args:
        user_id: 사용자 ID
        embed_tokens: 임베딩 토큰 수
        embedding_model: 임베딩 모델명
        run_id: 실행 ID
        session: DB 세션
        
    Returns:
        생성된 UsageMeter 레코드
    """
    return await record_usage(
        user_id=user_id,
        embed_tokens=embed_tokens,
        embedding_model=embedding_model,
        run_id=run_id,
        session=session
    )


async def record_llm_usage(
    user_id: int,
    in_tokens: int,
    out_tokens: int,
    llm_model: str = "gpt-3.5-turbo",
    cached_in_tokens: int = 0,
    run_id: Optional[UUID] = None,
    session: Optional[AsyncSession] = None
) -> UsageMeter:
    """
    LLM 전용 사용량 기록 (편의 함수)
    
    Args:
        user_id: 사용자 ID
        in_tokens: 입력 토큰 수
        out_tokens: 출력 토큰 수
        llm_model: LLM 모델명
        cached_in_tokens: 캐시된 입력 토큰 수
        run_id: 실행 ID
        session: DB 세션
        
    Returns:
        생성된 UsageMeter 레코드
    """
    return await record_usage(
        user_id=user_id,
        in_tokens=in_tokens,
        cached_in_tokens=cached_in_tokens,
        out_tokens=out_tokens,
        llm_model=llm_model,
        run_id=run_id,
        session=session
    )


async def get_monthly_usage(
    user_id: int,
    plan_month: date,
    session: Optional[AsyncSession] = None
) -> List[UsageMeter]:
    """
    특정 사용자의 월별 사용량 조회 (모든 모델 조합)
    
    Args:
        user_id: 사용자 ID
        plan_month: 조회할 월 (첫째 날)
        session: DB 세션
        
    Returns:
        해당 월의 사용량 레코드 리스트
    """
    close_session = False
    if session is None:
        session = await get_db().__anext__()
        close_session = True
    
    try:
        stmt = select(UsageMeter).where(
            UsageMeter.user_id == user_id,
            UsageMeter.plan_month == plan_month
        ).order_by(UsageMeter.created_at.desc())
        
        result = await session.execute(stmt)
        records = result.scalars().all()
        
        logger.debug(f"Retrieved {len(records)} usage records for user {user_id}, month {plan_month}")
        
        return list(records)
    finally:
        if close_session:
            await session.close()


async def get_total_monthly_wtu(
    user_id: int,
    plan_month: date,
    session: Optional[AsyncSession] = None
) -> int:
    """
    특정 사용자의 월별 총 WTU 계산
    
    Args:
        user_id: 사용자 ID
        plan_month: 조회할 월
        session: DB 세션
        
    Returns:
        해당 월의 총 WTU
    """
    records = await get_monthly_usage(user_id, plan_month, session)
    total_wtu = sum(record.wtu for record in records)
    
    logger.debug(f"Total monthly WTU for user {user_id}, month {plan_month}: {total_wtu}")
    
    return total_wtu


async def get_usage_by_model(
    user_id: int,
    plan_month: date,
    model_name: str,
    session: Optional[AsyncSession] = None
) -> List[UsageMeter]:
    """
    특정 모델의 사용량만 조회
    
    Args:
        user_id: 사용자 ID
        plan_month: 조회할 월
        model_name: 모델명 (LLM 또는 임베딩)
        session: DB 세션
        
    Returns:
        해당 모델의 사용량 레코드 리스트
    """
    close_session = False
    if session is None:
        session = await get_db().__anext__()
        close_session = True
    
    try:
        stmt = select(UsageMeter).where(
            UsageMeter.user_id == user_id,
            UsageMeter.plan_month == plan_month
        ).where(
            (UsageMeter.llm_model == model_name) | 
            (UsageMeter.embedding_model == model_name)
        ).order_by(UsageMeter.created_at.desc())
        
        result = await session.execute(stmt)
        records = result.scalars().all()
        
        logger.debug(f"Retrieved {len(records)} usage records for model {model_name}")
        
        return list(records)
    finally:
        if close_session:
            await session.close()
