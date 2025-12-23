"""티어 기반 LLM Fallback 로직

에이전트는 모델이 아닌 티어만 지정하면 자동으로 fallback이 처리됩니다.
Fallback 순서는 model_catalog 테이블에서 동적으로 조회합니다.
"""

from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

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
from app.domains.ai.repository import AIRepository

logger = get_logger(__name__)


async def call_with_fallback(
    tier: LLMTier,
    messages: list[LLMMessage],
    session: AsyncSession,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    **kwargs,
) -> LLMResult:
    """티어 기반 LLM 호출 (자동 fallback)

    첫 번째 모델이 실패하면 자동으로 다음 모델로 재시도합니다.
    모든 모델이 실패하면 AllProvidersFailedError를 발생시킵니다.
    Fallback 순서는 model_catalog 테이블에서 동적으로 조회합니다.

    Args:
        tier: LLM 티어 (light, standard, premium, search)
        messages: 대화 메시지
        session: DB 세션
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
            messages=messages,
            session=db_session
        )
        print(result.content)
    """
    # DB에서 티어별 모델 조회
    repo = AIRepository(session)
    models = await repo.get_models_by_tier(tier.value)

    if not models:
        raise ValueError(
            f"No available models for tier: {tier}. "
            "Please check model_catalog table."
        )

    attempted_models = []

    for model_info in models:
        model_alias = model_info.alias
        try:
            logger.info(
                f"Attempting LLM call with tier={tier}, model={model_alias}"
            )
            result = await acompletion_raw(
                model=model_alias,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            logger.info(f"LLM call succeeded with model={model_alias}")
            return result

        except LLMProviderError as e:
            attempted_models.append(model_alias)
            logger.warning(
                f"Model {model_alias} failed (tier={tier}): "
                f"{e.detail_info['error']}. Trying next model..."
            )
            continue

    # 모든 모델 실패
    raise AllProvidersFailedError(tier=tier.value, attempts=attempted_models)


async def stream_with_fallback(
    tier: LLMTier,
    messages: list[LLMMessage],
    session: AsyncSession,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    **kwargs,
) -> AsyncGenerator[str, None]:
    """티어 기반 스트리밍 호출 (스트리밍 시작 전까지만 fallback)

    스트리밍 시작 전 (첫 번째 청크 전)에 에러가 발생하면 다음 모델로
    fallback을 시도합니다. 스트리밍이 시작된 후에는 이미 yield된 청크를
    취소할 수 없으므로 즉시 에러를 발생시킵니다.

    Args:
        tier: LLM 티어
        messages: 대화 메시지
        session: DB 세션
        temperature: 샘플링 온도
        max_tokens: 최대 출력 토큰
        **kwargs: 추가 파라미터

    Yields:
        str: 생성된 텍스트 청크

    Raises:
        AllProvidersFailedError: 모든 모델이 스트리밍 시작 전 실패 시
        LLMProviderError: 스트리밍 중 에러 발생 시 (fallback 없음)

    Example:
        from app.core.llm import LLMTier, LLMMessage, stream_with_fallback

        messages = [LLMMessage(role="user", content="Write a story")]
        async for chunk in stream_with_fallback(
            tier=LLMTier.STANDARD,
            messages=messages,
            session=db_session
        ):
            print(chunk, end="", flush=True)

    Note:
        - 연결 실패, 인증 에러 등 초기 에러: fallback 시도
        - 스트리밍 중간 에러: 즉시 종료 (응답 손상 방지)
    """
    # DB에서 티어별 모델 조회
    repo = AIRepository(session)
    models = await repo.get_models_by_tier(tier.value)

    if not models:
        raise ValueError(
            f"No available models for tier: {tier}. "
            "Please check model_catalog table."
        )

    attempted_models = []
    streaming_started = False

    for model_info in models:
        model_alias = model_info.alias
        try:
            logger.info(
                f"Attempting streaming: tier={tier}, model={model_alias}"
            )

            async for chunk in astream_completion_raw(
                model=model_alias,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            ):
                # 첫 번째 청크를 성공적으로 받음 - 스트리밍 시작
                if not streaming_started:
                    streaming_started = True
                    logger.info(f"Streaming started with model={model_alias}")

                yield chunk

            # 스트리밍 성공 완료
            logger.info(f"Streaming completed with model={model_alias}")
            return

        except LLMProviderError as e:
            # 스트리밍이 시작된 후 에러: fallback 없이 즉시 종료
            if streaming_started:
                logger.error(
                    f"Streaming failed mid-stream with model={model_alias}: "
                    f"{e.detail_info['error']}. "
                    "Cannot fallback - chunks already sent."
                )
                raise

            # 스트리밍 시작 전 에러: fallback 시도
            attempted_models.append(model_alias)
            logger.warning(
                f"Model {model_alias} failed before streaming (tier={tier}): "
                f"{e.detail_info['error']}. Trying next model..."
            )
            continue

    # 모든 모델이 스트리밍 시작 전에 실패
    raise AllProvidersFailedError(tier=tier.value, attempts=attempted_models)


async def create_embedding(
    input_text: str, session: AsyncSession
) -> list[float]:
    """임베딩 생성 (fallback 없음)

    임베딩은 모델마다 벡터 공간이 다르므로 fallback을 지원하지 않습니다.
    실패 시 AI 도메인에서 키워드 검색으로 대체해야 합니다.
    사용할 모델은 model_catalog의 embedding 티어에서 조회합니다.

    Args:
        input_text: 임베딩할 텍스트
        session: DB 세션

    Returns:
        list[float]: 임베딩 벡터 (text-embedding-3-large: 3072 차원)

    Raises:
        LLMProviderError: 임베딩 생성 실패 시
        ValueError: embedding 티어에 사용 가능한 모델이 없는 경우

    Example:
        from app.core.llm import create_embedding

        vector = await create_embedding("Hello world", session=db_session)
        print(f"Embedding dimension: {len(vector)}")
    """
    # DB에서 embedding 티어 모델 조회
    repo = AIRepository(session)
    models = await repo.get_models_by_tier("embedding")

    if not models:
        raise ValueError(
            "No available embedding models. Please check model_catalog table."
        )

    # 첫 번째 모델 사용 (embedding은 fallback 없음)
    model_alias = models[0].alias
    logger.info(f"Creating embedding with model={model_alias}")
    return await aembedding_raw(model=model_alias, input_text=input_text)
