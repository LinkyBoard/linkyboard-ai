"""LangFuse 옵저버빌리티 연동

모든 LLM 호출을 자동으로 트레이싱합니다.
"""

import os
from typing import Optional

import litellm
from langfuse import Langfuse
from langfuse.decorators import observe

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def initialize_langfuse() -> Optional[Langfuse]:
    """LangFuse 클라이언트 초기화

    Returns:
        Langfuse: 초기화된 클라이언트 또는 None (실패 시)
    """
    try:
        # 환경 변수 설정 (LangFuse SDK가 자동으로 읽음)
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
        os.environ["LANGFUSE_HOST"] = settings.langfuse_host

        # LiteLLM success callback 등록
        litellm.success_callback = ["langfuse"]

        # LangFuse 클라이언트 생성
        langfuse = Langfuse(
            secret_key=settings.langfuse_secret_key,
            public_key=settings.langfuse_public_key,
            host=settings.langfuse_host,
        )

        logger.info("LangFuse initialized successfully")
        return langfuse

    except Exception as e:
        logger.warning(
            f"LangFuse initialization failed: {e}. "
            "Continuing without observability."
        )
        return None


# 전역 클라이언트 (모듈 로드 시 초기화)
langfuse_client = initialize_langfuse()


def get_observe_decorator():
    """LangFuse @observe 데코레이터 반환

    도메인 코드에서 이 함수를 사용하여 함수/메서드를 트레이싱할 수 있습니다.

    Example:
        from app.core.llm.observability import get_observe_decorator

        observe = get_observe_decorator()

        @observe()
        async def ask(request: AskRequest):
            ...

    Returns:
        observe 데코레이터 (LangFuse 사용 가능 시) 또는 no-op 데코레이터
    """
    if langfuse_client:
        return observe
    else:
        # LangFuse 없을 때는 no-op 데코레이터 반환
        def noop_observe(*args, **kwargs):
            def decorator(func):
                return func

            return decorator

        return noop_observe
