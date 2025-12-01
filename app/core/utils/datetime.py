"""날짜/시간 유틸리티"""

from datetime import datetime, timedelta, timezone
from typing import Optional

# 한국 시간대 (UTC+9)
KST = timezone(timedelta(hours=9))
UTC = timezone.utc


def now_utc() -> datetime:
    """현재 UTC 시간 반환"""
    return datetime.now(UTC)


def now_kst() -> datetime:
    """현재 한국 시간 반환"""
    return datetime.now(KST)


def utc_to_kst(dt: datetime) -> datetime:
    """UTC를 한국 시간으로 변환"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(KST)


def kst_to_utc(dt: datetime) -> datetime:
    """한국 시간을 UTC로 변환"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    return dt.astimezone(UTC)


def format_datetime(
    dt: datetime,
    fmt: str = "%Y-%m-%d %H:%M:%S",
) -> str:
    """datetime을 문자열로 포맷"""
    return dt.strftime(fmt)


def parse_datetime(
    date_str: str,
    fmt: str = "%Y-%m-%d %H:%M:%S",
) -> Optional[datetime]:
    """문자열을 datetime으로 파싱"""
    try:
        return datetime.strptime(date_str, fmt)
    except ValueError:
        return None


def format_iso(dt: datetime) -> str:
    """ISO 8601 형식으로 포맷"""
    return dt.isoformat()


def parse_iso(date_str: str) -> Optional[datetime]:
    """ISO 8601 형식 문자열 파싱"""
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return None


def start_of_day(dt: Optional[datetime] = None) -> datetime:
    """해당 날짜의 시작 시간 (00:00:00)"""
    if dt is None:
        dt = now_utc()
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day(dt: Optional[datetime] = None) -> datetime:
    """해당 날짜의 종료 시간 (23:59:59)"""
    if dt is None:
        dt = now_utc()
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


def days_ago(days: int) -> datetime:
    """n일 전 시간 반환"""
    return now_utc() - timedelta(days=days)


def days_later(days: int) -> datetime:
    """n일 후 시간 반환"""
    return now_utc() + timedelta(days=days)


def time_since(dt: datetime) -> str:
    """경과 시간을 사람이 읽기 쉬운 형태로 반환"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    diff = now_utc() - dt
    seconds = diff.total_seconds()

    if seconds < 60:
        return "방금 전"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes}분 전"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours}시간 전"
    elif seconds < 604800:
        days = int(seconds // 86400)
        return f"{days}일 전"
    elif seconds < 2592000:
        weeks = int(seconds // 604800)
        return f"{weeks}주 전"
    elif seconds < 31536000:
        months = int(seconds // 2592000)
        return f"{months}개월 전"
    else:
        years = int(seconds // 31536000)
        return f"{years}년 전"
