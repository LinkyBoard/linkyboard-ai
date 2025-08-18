"""
사용량 기록 및 조회 서비스

WTU 사용량을 데이터베이스에 기록하고 조회합니다.
"""

import logging
import uuid
from datetime import date, datetime
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.models import UsageMeter, ModelCatalog
from app.metrics.wtu_calculator import calculate_embedding_wtu, calculate_llm_wtu

logger = logging.getLogger(__name__)


async def record_embedding_usage(
    user_id: int,
    embed_tokens: int,
    embedding_model: str = "text-embedding-3-small",
    run_id: Optional[UUID] = None,
    board_id: Optional[int] = None,
    session: Optional[AsyncSession] = None
) -> UsageMeter:
    """
    임베딩 사용량을 usage_meter 테이블에 기록
    
    Args:
        user_id: 사용자 ID
        embed_tokens: 임베딩 토큰 수
        embedding_model: 임베딩 모델명
        run_id: 실행 ID (선택사항)
        board_id: 보드 ID (선택사항)
        session: 데이터베이스 세션 (선택사항)
        
    Returns:
        생성된 UsageMeter 객체
    """
    close_session = False
    if session is None:
        session = AsyncSessionLocal()
        close_session = True
    
    try:
        # WTU 계산
        wtu, estimated_cost_from_wtu = await calculate_embedding_wtu(embed_tokens, embedding_model)
        
        # 추정 비용 계산 (USD)
        # text-embedding-3-small: $0.02 per 1M tokens
        estimated_cost_usd = (embed_tokens / 1_000_000) * 0.02
        
        # 현재 월 계산
        current_date = date.today()
        plan_month = current_date.replace(day=1)
        
        # 모델 카탈로그에서 선택된 모델 ID 조회
        stmt = select(ModelCatalog).where(
            ModelCatalog.model_name == embedding_model,
            ModelCatalog.model_type == "embedding",
            ModelCatalog.is_active == True
        )
        result = await session.execute(stmt)
        selected_model = result.scalar_one_or_none()
        
        # 사용량 기록 생성
        usage_record = UsageMeter(
            id=uuid.uuid4(),
            user_id=user_id,
            run_id=run_id,
            embedding_model=embedding_model,
            selected_model_id=selected_model.id if selected_model else None,
            board_id=board_id,
            embed_tokens=embed_tokens,
            wtu=wtu,
            estimated_cost_usd=estimated_cost_usd,
            plan_month=plan_month
        )
        
        session.add(usage_record)
        await session.commit()
        await session.refresh(usage_record)
        
        logger.info(f"Recorded embedding usage: user_id={user_id}, tokens={embed_tokens}, wtu={wtu}")
        return usage_record
        
    except Exception as e:
        logger.error(f"Failed to record embedding usage: {e}")
        if session:
            await session.rollback()
        raise
        
    finally:
        if close_session:
            await session.aclose()


async def record_llm_usage(
    user_id: int,
    in_tokens: int,
    out_tokens: int,
    llm_model: str = "gpt-4o-mini",
    cached_in_tokens: int = 0,
    run_id: Optional[UUID] = None,
    board_id: Optional[int] = None,
    session: Optional[AsyncSession] = None
) -> UsageMeter:
    """
    LLM 사용량을 usage_meter 테이블에 기록
    
    Args:
        user_id: 사용자 ID
        in_tokens: 입력 토큰 수
        out_tokens: 출력 토큰 수
        llm_model: LLM 모델명
        cached_in_tokens: 캐시된 입력 토큰 수
        run_id: 실행 ID (선택사항)
        board_id: 보드 ID (선택사항)
        session: 데이터베이스 세션 (선택사항)
        
    Returns:
        생성된 UsageMeter 객체
    """
    close_session = False
    if session is None:
        session = AsyncSessionLocal()
        close_session = True
    
    try:
        # WTU 계산
        wtu, estimated_cost_from_wtu = await calculate_llm_wtu(in_tokens, out_tokens, cached_in_tokens, llm_model)
        
        # 추정 비용 계산 (USD)
        # gpt-4o-mini: $0.15 per 1M input tokens, $0.60 per 1M output tokens
        if llm_model == "gpt-4o-mini":
            input_cost = (in_tokens / 1_000_000) * 0.15
            output_cost = (out_tokens / 1_000_000) * 0.60
            estimated_cost_usd = input_cost + output_cost
        else:
            # 기본값 (gpt-3.5-turbo 기준)
            input_cost = (in_tokens / 1_000_000) * 0.50
            output_cost = (out_tokens / 1_000_000) * 1.50
            estimated_cost_usd = input_cost + output_cost
        
        # 현재 월 계산
        current_date = date.today()
        plan_month = current_date.replace(day=1)
        
        # 모델 카탈로그에서 선택된 모델 ID 조회
        stmt = select(ModelCatalog).where(
            ModelCatalog.model_name == llm_model,
            ModelCatalog.model_type == "llm",
            ModelCatalog.is_active == True
        )
        result = await session.execute(stmt)
        selected_model = result.scalar_one_or_none()
        
        # 사용량 기록 생성
        usage_record = UsageMeter(
            id=uuid.uuid4(),
            user_id=user_id,
            run_id=run_id,
            llm_model=llm_model,
            selected_model_id=selected_model.id if selected_model else None,
            board_id=board_id,
            in_tokens=in_tokens,
            cached_in_tokens=cached_in_tokens,
            out_tokens=out_tokens,
            wtu=wtu,
            estimated_cost_usd=estimated_cost_usd,
            plan_month=plan_month
        )
        
        session.add(usage_record)
        await session.commit()
        await session.refresh(usage_record)
        
        logger.info(f"Recorded LLM usage: user_id={user_id}, in_tokens={in_tokens}, out_tokens={out_tokens}, wtu={wtu}")
        return usage_record
        
    except Exception as e:
        logger.error(f"Failed to record LLM usage: {e}")
        if session:
            await session.rollback()
        raise
        
    finally:
        if close_session:
            await session.aclose()


async def get_user_monthly_wtu(
    user_id: int,
    plan_month: date,
    session: Optional[AsyncSession] = None
) -> int:
    """
    사용자의 월간 WTU 사용량 조회
    
    Args:
        user_id: 사용자 ID
        plan_month: 계획 월 (YYYY-MM-01 형식)
        session: 데이터베이스 세션 (선택사항)
        
    Returns:
        해당 월의 총 WTU 사용량
    """
    close_session = False
    if session is None:
        session = AsyncSessionLocal()
        close_session = True
    
    try:
        stmt = select(func.sum(UsageMeter.wtu)).where(
            UsageMeter.user_id == user_id,
            UsageMeter.plan_month == plan_month
        )
        result = await session.execute(stmt)
        total_wtu = result.scalar()
        
        return total_wtu or 0
        
    finally:
        if close_session:
            await session.aclose()


async def get_board_total_monthly_wtu(
    board_id: int,
    plan_month: date,
    session: Optional[AsyncSession] = None
) -> int:
    """
    보드의 월간 총 WTU 사용량 조회
    
    Args:
        board_id: 보드 ID
        plan_month: 계획 월 (YYYY-MM-01 형식)
        session: 데이터베이스 세션 (선택사항)
        
    Returns:
        해당 월의 보드 총 WTU 사용량
    """
    close_session = False
    if session is None:
        session = AsyncSessionLocal()
        close_session = True
    
    try:
        stmt = select(func.sum(UsageMeter.wtu)).where(
            UsageMeter.board_id == board_id,
            UsageMeter.plan_month == plan_month
        )
        result = await session.execute(stmt)
        total_wtu = result.scalar()
        
        return total_wtu or 0
        
    finally:
        if close_session:
            await session.aclose()


async def get_usage_statistics(
    user_id: Optional[int] = None,
    board_id: Optional[int] = None,
    plan_month: Optional[date] = None,
    session: Optional[AsyncSession] = None
) -> Dict[str, Any]:
    """
    사용량 통계 조회
    
    Args:
        user_id: 사용자 ID (선택사항)
        board_id: 보드 ID (선택사항)
        plan_month: 계획 월 (선택사항)
        session: 데이터베이스 세션 (선택사항)
        
    Returns:
        사용량 통계 딕셔너리
    """
    close_session = False
    if session is None:
        session = AsyncSessionLocal()
        close_session = True
    
    try:
        # 기본 쿼리
        stmt = select(
            func.sum(UsageMeter.wtu).label("total_wtu"),
            func.sum(UsageMeter.in_tokens).label("total_in_tokens"),
            func.sum(UsageMeter.out_tokens).label("total_out_tokens"),
            func.sum(UsageMeter.embed_tokens).label("total_embed_tokens"),
            func.sum(UsageMeter.estimated_cost_usd).label("total_cost_usd"),
            func.count(UsageMeter.id).label("total_requests")
        )
        
        # 필터 조건 추가
        if user_id:
            stmt = stmt.where(UsageMeter.user_id == user_id)
        if board_id:
            stmt = stmt.where(UsageMeter.board_id == board_id)
        if plan_month:
            stmt = stmt.where(UsageMeter.plan_month == plan_month)
        
        result = await session.execute(stmt)
        row = result.first()
        
        return {
            "total_wtu": row.total_wtu or 0,
            "total_in_tokens": row.total_in_tokens or 0,
            "total_out_tokens": row.total_out_tokens or 0,
            "total_embed_tokens": row.total_embed_tokens or 0,
            "total_cost_usd": float(row.total_cost_usd) if row.total_cost_usd else 0.0,
            "total_requests": row.total_requests or 0
        }
        
    finally:
        if close_session:
            await session.aclose()