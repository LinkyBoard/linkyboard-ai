"""시간 측정 유틸리티 테스트"""

import time

import pytest

from app.core.utils.time import (
    calculate_elapsed_time_ms,
    get_current_time_ms,
    measure_time,
)


def test_get_current_time_ms():
    """현재 시간 측정 테스트"""
    time1 = get_current_time_ms()
    time.sleep(0.01)  # 10ms 대기
    time2 = get_current_time_ms()

    # time2가 time1보다 커야 함
    assert time2 > time1
    # 약 10ms 이상 차이가 나야 함
    assert (time2 - time1) >= 10


def test_calculate_elapsed_time_ms():
    """경과 시간 계산 테스트"""
    start_time = time.perf_counter()
    time.sleep(0.05)  # 50ms 대기
    elapsed = calculate_elapsed_time_ms(start_time)

    # 약 50ms 이상이어야 함
    assert elapsed >= 50
    # 100ms를 초과하지 않아야 함 (오차 범위)
    assert elapsed < 100


def test_measure_time_context_manager():
    """measure_time 컨텍스트 매니저 테스트"""
    with measure_time() as timer:
        # 초기값은 0
        assert timer["elapsed_ms"] == 0.0
        time.sleep(0.03)  # 30ms 대기

    # 컨텍스트 종료 후 경과 시간이 기록됨
    assert timer["elapsed_ms"] >= 30
    assert timer["elapsed_ms"] < 60


def test_measure_time_with_exception():
    """예외 발생 시에도 시간이 측정되는지 테스트"""
    with pytest.raises(ValueError):
        with measure_time() as timer:
            time.sleep(0.02)  # 20ms 대기
            raise ValueError("Test error")

    # 예외가 발생해도 시간은 측정됨
    assert timer["elapsed_ms"] >= 20


def test_measure_time_nested():
    """중첩된 measure_time 테스트"""
    with measure_time() as outer_timer:
        time.sleep(0.01)  # 10ms

        with measure_time() as inner_timer:
            time.sleep(0.02)  # 20ms

        # 내부 타이머는 약 20ms
        assert inner_timer["elapsed_ms"] >= 20
        assert inner_timer["elapsed_ms"] < 40

    # 외부 타이머는 약 30ms (10 + 20)
    assert outer_timer["elapsed_ms"] >= 30
    assert outer_timer["elapsed_ms"] < 60
