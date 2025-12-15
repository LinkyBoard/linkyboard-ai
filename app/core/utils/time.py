"""시간 측정 유틸리티"""

import time
from contextlib import contextmanager
from typing import Generator


def get_current_time_ms() -> float:
    """현재 시간을 밀리초로 반환

    Returns:
        float: 현재 시간 (밀리초)
    """
    return time.perf_counter() * 1000


def calculate_elapsed_time_ms(start_time: float) -> float:
    """시작 시간으로부터 경과 시간을 밀리초로 계산

    Args:
        start_time: perf_counter() 시작 시간

    Returns:
        float: 경과 시간 (밀리초)
    """
    return (time.perf_counter() - start_time) * 1000


@contextmanager
def measure_time() -> Generator[dict[str, float], None, None]:
    """처리 시간을 측정하는 컨텍스트 매니저

    Usage:
        with measure_time() as timer:
            # 시간을 측정할 코드
            ...
        elapsed_ms = timer["elapsed_ms"]

    Yields:
        dict: elapsed_ms 키를 포함하는 딕셔너리
    """
    timer = {"elapsed_ms": 0.0}
    start = time.perf_counter()
    try:
        yield timer
    finally:
        timer["elapsed_ms"] = (time.perf_counter() - start) * 1000
