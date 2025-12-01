"""요청 ID 컨텍스트 관리"""

import contextvars
import uuid
from typing import Optional

# 요청 ID를 저장하는 컨텍스트 변수
request_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)


def get_request_id() -> Optional[str]:
    """현재 요청 ID 반환"""
    return request_id_ctx.get()


def set_request_id(request_id: Optional[str] = None) -> str:
    """요청 ID 설정 (없으면 새로 생성)"""
    if request_id is None:
        request_id = str(uuid.uuid4())
    request_id_ctx.set(request_id)
    return request_id


def generate_request_id() -> str:
    """새 요청 ID 생성"""
    return str(uuid.uuid4())
