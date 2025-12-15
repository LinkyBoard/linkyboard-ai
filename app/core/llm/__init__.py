"""Core LLM 인프라 공개 API

이 모듈은 Topics/AI 도메인에서 사용할 공개 인터페이스만 노출합니다.
"""

from app.core.llm.fallback import (
    call_with_fallback,
    create_embedding,
    stream_with_fallback,
)
from app.core.llm.observability import get_observe_decorator
from app.core.llm.types import LLMMessage, LLMResult, LLMTier

__all__ = [
    # Types
    "LLMTier",
    "LLMMessage",
    "LLMResult",
    # Functions
    "call_with_fallback",
    "stream_with_fallback",
    "create_embedding",
    # Decorators
    "get_observe_decorator",
]
