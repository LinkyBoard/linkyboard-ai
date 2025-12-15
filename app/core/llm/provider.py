"""LiteLLM 기반 LLM 프로바이더 래퍼

이 모듈은 LiteLLM을 직접 호출하는 유일한 곳입니다.
나중에 LangGraph 등으로 마이그레이션 시 이 파일만 교체하면 됩니다.
"""

import os
from typing import AsyncGenerator, Optional, cast

from litellm import acompletion, aembedding

from app.core.config import settings
from app.core.llm.types import LLMMessage, LLMProviderError, LLMResult
from app.core.logging import get_logger

logger = get_logger(__name__)


def _setup_api_keys() -> None:
    """환경 변수에 API 키 설정 (LiteLLM이 자동으로 읽음)"""
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    os.environ["GOOGLE_API_KEY"] = settings.google_api_key
    os.environ["PERPLEXITY_API_KEY"] = settings.perplexity_api_key


# 모듈 로드 시 API 키 설정
_setup_api_keys()


async def acompletion_raw(
    model: str,
    messages: list[LLMMessage],
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    **kwargs,
) -> LLMResult:
    """LiteLLM completion 호출 (비동기)

    Args:
        model: 모델 alias (예: "claude-4.5-haiku", "gpt-4.1-mini")
        messages: 대화 메시지 리스트
        temperature: 샘플링 온도 (0.0 ~ 1.0)
        max_tokens: 최대 출력 토큰 수
        **kwargs: LiteLLM에 전달할 추가 파라미터

    Returns:
        LLMResult: 생성된 텍스트 및 사용량 정보

    Raises:
        LLMProviderError: 프로바이더 호출 실패 시

    Example:
        messages = [
            LLMMessage(role="system", content="You are helpful."),
            LLMMessage(role="user", content="Hello!")
        ]
        result = await acompletion_raw("claude-4.5-haiku", messages)
    """
    try:
        response = await acompletion(
            model=model,
            messages=[msg.model_dump() for msg in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        choice = response.choices[0]
        usage = response.usage

        return LLMResult(
            content=choice.message.content,
            model=response.model,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            finish_reason=choice.finish_reason,
        )

    except Exception as e:
        logger.error(f"LiteLLM completion failed for model {model}: {e}")
        raise LLMProviderError(provider=model, original_error=str(e))


async def astream_completion_raw(
    model: str,
    messages: list[LLMMessage],
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    **kwargs,
) -> AsyncGenerator[str, None]:
    """LiteLLM streaming completion (비동기 제너레이터)

    Args:
        model: 모델 alias
        messages: 대화 메시지 리스트
        temperature: 샘플링 온도
        max_tokens: 최대 출력 토큰 수
        **kwargs: LiteLLM 추가 파라미터

    Yields:
        str: 생성된 텍스트 청크

    Raises:
        LLMProviderError: 프로바이더 호출 실패 시

    Example:
        messages = [LLMMessage(role="user", content="Write a story")]
        async for chunk in astream_completion_raw("gpt-4.1-mini", messages):
            print(chunk, end="", flush=True)
    """
    try:
        response = await acompletion(
            model=model,
            messages=[msg.model_dump() for msg in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )

        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    except Exception as e:
        logger.error(f"LiteLLM streaming failed for model {model}: {e}")
        raise LLMProviderError(provider=model, original_error=str(e))


async def aembedding_raw(model: str, input_text: str) -> list[float]:
    """LiteLLM embedding 생성 (비동기)

    Args:
        model: 임베딩 모델 alias (예: "text-embedding-3-large")
        input_text: 임베딩할 텍스트

    Returns:
        list[float]: 임베딩 벡터

    Raises:
        LLMProviderError: 프로바이더 호출 실패 시

    Example:
        vector = await aembedding_raw(
            "text-embedding-3-large",
            "Hello world"
        )
        # vector: list[float] with 3072 dimensions
    """
    try:
        response = await aembedding(model=model, input=[input_text])
        return cast(list[float], response.data[0]["embedding"])

    except Exception as e:
        logger.error(f"LiteLLM embedding failed for model {model}: {e}")
        raise LLMProviderError(provider=model, original_error=str(e))
