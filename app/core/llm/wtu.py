"""WTU (Weighted Token Unit) 계산 유틸리티

WTU는 모델별 비용 차이를 반영한 표준화된 사용량 단위입니다.
입력/출력 토큰은 가격이 다르므로 별도의 가중치를 적용합니다.
"""

import math

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domains.ai.repository import AIRepository

logger = get_logger(__name__)


async def calculate_wtu_from_tokens(
    input_tokens: int,
    output_tokens: int,
    model: str,
    session: AsyncSession,
) -> int:
    """토큰 수를 WTU로 변환 (입출력 별도 가중치 적용)

    Args:
        input_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수
        model: 사용된 모델 별칭
        session: DB 세션

    Returns:
        int: 계산된 WTU (최소 1)

    Note:
        - 입력/출력 토큰은 가격이 다르므로 별도 가중치 적용
        - 기준 모델(claude-4.5-haiku): input_multiplier=1.0, output=1.0
        - WTU = ceil((in_tokens/1000)*in_mult + (out_tokens/1000)*out_mult)
        - 최소 1 WTU 보장

    Example::

        # claude-4.5-haiku (입력 1.0x, 출력 1.0x)
        wtu = await calculate_wtu_from_tokens(
            input_tokens=1500,
            output_tokens=500,
            model="claude-4.5-haiku",
            session=db_session
        )
        # wtu = ceil(1.5*1.0 + 0.5*1.0) = ceil(2.0) = 2

        # claude-4.5-sonnet (입력 3.0x, 출력 3.0x)
        wtu = await calculate_wtu_from_tokens(
            input_tokens=1500,
            output_tokens=500,
            model="claude-4.5-sonnet",
            session=db_session
        )
        # wtu = ceil(1.5*3.0 + 0.5*3.0) = ceil(6.0) = 6
    """
    # model_catalog에서 모델 정보 조회
    repo = AIRepository(session)
    model_info = await repo.get_model_by_alias(model)

    if not model_info:
        logger.warning(f"Model {model} not in catalog, using default 1.0x")
        input_multiplier = 1.0
        output_multiplier = 1.0
    else:
        input_multiplier = float(model_info.input_wtu_multiplier or 1.0)
        output_multiplier = float(model_info.output_wtu_multiplier or 1.0)

    # 입력/출력 WTU 별도 계산
    input_wtu = (input_tokens / 1000) * input_multiplier
    output_wtu = (output_tokens / 1000) * output_multiplier

    # 합산 후 올림
    total_wtu = math.ceil(input_wtu + output_wtu)

    # 최소 1 WTU 보장
    return max(1, total_wtu)
