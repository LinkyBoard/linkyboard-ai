"""티어 기반 LLM Fallback 로직

에이전트는 모델이 아닌 티어만 지정하면 자동으로 fallback이 처리됩니다.
"""

from typing import AsyncGenerator, Optional

from app.core.llm.provider import (
    acompletion_raw,
    aembedding_raw,
    astream_completion_raw,
)
from app.core.llm.types import (
    AllProvidersFailedError,
    LLMMessage,
    LLMProviderError,
    LLMResult,
    LLMTier,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


# 티어별 fallback 순서 (orchestration-spec.md 기준)
FALLBACK_ORDER: dict[str, list[str]] = {
    "light": ["claude-4.5-haiku", "gpt-4.1-mini", "gemini-2.0-flash"],
    "standard": ["gpt-5-mini", "gpt-4.1", "claude-4.5-sonnet"],
    "premium": ["gpt-5", "claude-4.5-opus"],
    "search": ["pplx-70b-online", "pplx-online-mini"],
    "embedding": ["text-embedding-3-large"],  # No fallback
}


async def call_with_fallback(
    tier: LLMTier,
    messages: list[LLMMessage],
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    **kwargs,
) -> LLMResult:
    """티어 기반 LLM 호출 (자동 fallback)

    첫 번째 모델이 실패하면 자동으로 다음 모델로 재시도합니다.
    모든 모델이 실패하면 AllProvidersFailedError를 발생시킵니다.

    Args:
        tier: LLM 티어 (light, standard, premium, search)
        messages: 대화 메시지
        temperature: 샘플링 온도
        max_tokens: 최대 출력 토큰
        **kwargs: 추가 파라미터

    Returns:
        LLMResult: 생성 결과

    Raises:
        AllProvidersFailedError: 모든 모델 실패 시

    Example:
        from app.core.llm import LLMTier, LLMMessage, call_with_fallback

        messages = [
            LLMMessage(role="system", content="You are helpful."),
            LLMMessage(role="user", content="Hello!")
        ]
        result = await call_with_fallback(
            tier=LLMTier.LIGHT,
            messages=messages
        )
        print(result.content)
    """
    models = FALLBACK_ORDER.get(tier.value, [])
    if not models:
        raise ValueError(f"Unknown LLM tier: {tier}")

    attempted_models = []

    for model in models:
        try:
            logger.info(f"Attempting LLM call with tier={tier}, model={model}")
            result = await acompletion_raw(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            logger.info(f"LLM call succeeded with model={model}")
            return result

        except LLMProviderError as e:
            attempted_models.append(model)
            logger.warning(
                f"Model {model} failed (tier={tier}): "
                f"{e.detail_info['error']}. Trying next model..."
            )
            continue

    # 모든 모델 실패
    raise AllProvidersFailedError(tier=tier.value, attempts=attempted_models)


async def stream_with_fallback(
    tier: LLMTier,
    messages: list[LLMMessage],
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    **kwargs,
) -> AsyncGenerator[str, None]:
    """티어 기반 스트리밍 호출 (자동 fallback)

    첫 번째 모델이 실패하면 자동으로 다음 모델로 재시도합니다.
    모든 모델이 실패하면 AllProvidersFailedError를 발생시킵니다.

    Args:
        tier: LLM 티어
        messages: 대화 메시지
        temperature: 샘플링 온도
        max_tokens: 최대 출력 토큰
        **kwargs: 추가 파라미터

    Yields:
        str: 생성된 텍스트 청크

    Raises:
        AllProvidersFailedError: 모든 모델 실패 시

    Example:
        from app.core.llm import LLMTier, LLMMessage, stream_with_fallback

        messages = [LLMMessage(role="user", content="Write a story")]
        async for chunk in stream_with_fallback(
            tier=LLMTier.STANDARD,
            messages=messages
        ):
            print(chunk, end="", flush=True)
    """
    models = FALLBACK_ORDER.get(tier.value, [])
    if not models:
        raise ValueError(f"Unknown LLM tier: {tier}")

    attempted_models = []

    for model in models:
        try:
            logger.info(
                f"Attempting streaming call with tier={tier}, model={model}"
            )
            async for chunk in astream_completion_raw(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            ):
                yield chunk
            logger.info(f"Streaming call succeeded with model={model}")
            return  # 성공 시 종료

        except LLMProviderError as e:
            attempted_models.append(model)
            logger.warning(
                f"Streaming model {model} failed (tier={tier}): "
                f"{e.detail_info['error']}. Trying next model..."
            )
            continue

    # 모든 모델 실패
    raise AllProvidersFailedError(tier=tier.value, attempts=attempted_models)


async def create_embedding(input_text: str) -> list[float]:
    """임베딩 생성 (fallback 없음)

    임베딩은 모델마다 벡터 공간이 다르므로 fallback을 지원하지 않습니다.
    실패 시 AI 도메인에서 키워드 검색으로 대체해야 합니다.

    Args:
        input_text: 임베딩할 텍스트

    Returns:
        list[float]: 임베딩 벡터 (text-embedding-3-large: 3072 차원)

    Raises:
        LLMProviderError: 임베딩 생성 실패 시

    Example:
        from app.core.llm import create_embedding

        vector = await create_embedding("Hello world")
        print(f"Embedding dimension: {len(vector)}")
    """
    model = FALLBACK_ORDER["embedding"][0]
    logger.info(f"Creating embedding with model={model}")
    return await aembedding_raw(model=model, input_text=input_text)
