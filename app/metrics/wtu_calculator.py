"""
WTU (Work Time Unit) 계산기

모델별 가중치를 사용하여 WTU를 계산합니다.
WTU 공식: WTU = in_tokens * w_in + cached_in_tokens * w_cached_in + out_tokens * w_out + embed_tokens * w_embed

기준 모델: GPT-5 mini (입력 $0.25/M, 출력 $2.00/M)
"""

import logging
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from .pricing_service import pricing_service

logger = logging.getLogger(__name__)


async def calculate_wtu(
    in_tokens: int = 0,
    cached_in_tokens: int = 0,
    out_tokens: int = 0,
    embed_tokens: int = 0,
    llm_model: Optional[str] = None,
    embedding_model: Optional[str] = None,
    session: Optional[AsyncSession] = None
) -> Tuple[int, float]:
    """
    모델별 가중치를 사용한 WTU 계산
    
    Args:
        in_tokens: 입력 토큰 수
        cached_in_tokens: 캐시된 입력 토큰 수
        out_tokens: 출력 토큰 수
        embed_tokens: 임베딩 토큰 수
        llm_model: LLM 모델명
        embedding_model: 임베딩 모델명
        session: DB 세션
        
    Returns:
        (WTU 값, 추정 비용 USD)
    """
    # 모델별 가중치 조회
    weights = await pricing_service.get_wtu_weights(llm_model, embedding_model, session)
    
    wtu = (
        in_tokens * weights['w_in'] +
        cached_in_tokens * weights['w_cached_in'] +
        out_tokens * weights['w_out'] +
        embed_tokens * weights['w_embed']
    )
    
    # 추정 비용 계산 (기준 모델 기준)
    estimated_cost = (
        (in_tokens * 0.25 / 1_000_000) +  # GPT-5 mini 입력 가격
        (out_tokens * 2.00 / 1_000_000)   # GPT-5 mini 출력 가격
    ) * (wtu / (in_tokens * 1.0 + out_tokens * 8.0)) if (in_tokens + out_tokens) > 0 else 0.0
    
    logger.debug(
        f"WTU calculation - Models: {llm_model}/{embedding_model}, "
        f"Tokens: in={in_tokens}, cached_in={cached_in_tokens}, out={out_tokens}, embed={embed_tokens}, "
        f"Weights: {weights}, WTU={int(wtu)}, Cost=${estimated_cost:.4f}"
    )
    
    return int(wtu), estimated_cost


def calculate_wtu_simple(
    in_tokens: int = 0,
    cached_in_tokens: int = 0,
    out_tokens: int = 0,
    embed_tokens: int = 0,
    alpha_embed: Optional[float] = None
) -> int:
    """
    단순 WTU 계산 (하위 호환성용)
    
    기본 가중치를 사용한 WTU 계산:
    - 입력: 1.0
    - 캐시 입력: 0.1
    - 출력: 8.0
    - 임베딩: alpha_embed (기본값: settings.WTU_ALPHA_EMBED)
    
    Args:
        in_tokens: 입력 토큰 수
        cached_in_tokens: 캐시된 입력 토큰 수
        out_tokens: 출력 토큰 수
        embed_tokens: 임베딩 토큰 수
        alpha_embed: 임베딩 가중치 (기본값은 설정에서 읽음)
        
    Returns:
        계산된 WTU 값
    """
    if alpha_embed is None:
        alpha_embed = settings.WTU_ALPHA_EMBED
    
    wtu = (
        in_tokens * 1 +
        cached_in_tokens * 0.1 +
        out_tokens * 8 +
        embed_tokens * alpha_embed
    )
    
    logger.debug(
        f"Simple WTU calculation - "
        f"in={in_tokens}, cached_in={cached_in_tokens}, out={out_tokens}, embed={embed_tokens}, "
        f"alpha={alpha_embed}, WTU={int(wtu)}"
    )
    
    return int(wtu)


async def calculate_embedding_wtu(
    embed_tokens: int,
    embedding_model: str = "text-embedding-3-small",
    session: Optional[AsyncSession] = None
) -> Tuple[int, float]:
    """
    임베딩 전용 WTU 계산 (편의 함수)
    
    Args:
        embed_tokens: 임베딩 토큰 수
        embedding_model: 임베딩 모델명
        session: DB 세션
        
    Returns:
        (WTU 값, 추정 비용 USD)
    """
    return await calculate_wtu(
        embed_tokens=embed_tokens,
        embedding_model=embedding_model,
        session=session
    )


async def calculate_llm_wtu(
    in_tokens: int,
    out_tokens: int,
    cached_in_tokens: int = 0,
    llm_model: str = "gpt-3.5-turbo",
    session: Optional[AsyncSession] = None
) -> Tuple[int, float]:
    """
    LLM 전용 WTU 계산 (편의 함수)
    
    Args:
        in_tokens: 입력 토큰 수
        out_tokens: 출력 토큰 수
        cached_in_tokens: 캐시된 입력 토큰 수
        llm_model: LLM 모델명
        session: DB 세션
        
    Returns:
        (WTU 값, 추정 비용 USD)
    """
    return await calculate_wtu(
        in_tokens=in_tokens,
        cached_in_tokens=cached_in_tokens,
        out_tokens=out_tokens,
        llm_model=llm_model,
        session=session
    )
