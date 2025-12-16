"""WTU (Weighted Token Unit) 계산 유틸리티

WTU는 모델별 비용 차이를 반영한 표준화된 사용량 단위입니다.
"""


def calculate_wtu_from_tokens(
    input_tokens: int,
    output_tokens: int,
    model: str = "gpt-4o-mini",
) -> int:
    """토큰 수를 WTU로 변환

    Args:
        input_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수
        model: 사용된 모델명

    Returns:
        int: 계산된 WTU

    Note:
        현재는 간단히 1000 토큰당 1 WTU로 계산합니다.
        Phase 2에서 model_catalog 테이블과 연동하여
        모델별 가중치(wtu_multiplier)를 적용할 예정입니다.

    Example::

        wtu = calculate_wtu_from_tokens(
            input_tokens=1500,
            output_tokens=500,
            model="gpt-4o-mini"
        )
        # wtu = 2 (2000 tokens / 1000)

    TODO: model_catalog 테이블 연동
        - model_catalog에서 wtu_multiplier 조회
        - 가중치 적용: base_wtu * multiplier
    """
    total_tokens = input_tokens + output_tokens
    base_wtu = total_tokens / 1000

    # TODO: Phase 2에서 모델별 가중치 적용
    # from app.domains.ai.repository import get_model_wtu_multiplier
    # multiplier = await get_model_wtu_multiplier(model)
    # return int(base_wtu * multiplier)

    return int(base_wtu) if base_wtu >= 1 else 1  # 최소 1 WTU
