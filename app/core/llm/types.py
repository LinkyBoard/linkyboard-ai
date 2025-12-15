"""LLM 관련 공통 타입 정의"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel

from app.core.exceptions import ErrorCode, InternalServerException


class LLMTier(str, Enum):
    """LLM 티어 (작업 복잡도 기반)

    Attributes:
        LIGHT: 간단한 작업 (요약, 분류)
        STANDARD: 일반 작업 (비교 분석, 글 작성)
        PREMIUM: 고급 작업 (복잡한 추론, 논리 구조화)
        SEARCH: 웹 검색 (Perplexity)
        EMBEDDING: 임베딩 생성
    """

    LIGHT = "light"
    STANDARD = "standard"
    PREMIUM = "premium"
    SEARCH = "search"
    EMBEDDING = "embedding"


class LLMMessage(BaseModel):
    """LLM 메시지 형식

    Attributes:
        role: 메시지 역할 ("system", "user", "assistant")
        content: 메시지 내용
    """

    role: str
    content: str


class LLMResult(BaseModel):
    """LLM 호출 결과

    Attributes:
        content: 생성된 텍스트
        model: 사용된 모델 이름
        input_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수
        finish_reason: 생성 완료 이유 (선택사항)
    """

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    finish_reason: Optional[str] = None


class LLMProviderError(InternalServerException):
    """단일 LLM 프로바이더 호출 실패

    단일 모델 호출이 실패했을 때 발생하는 예외입니다.
    Fallback 로직에서 다음 모델로 재시도하기 위해 사용됩니다.

    Example:
        try:
            result = await litellm.acompletion(model="claude-4.5-haiku", ...)
        except Exception as e:
            raise LLMProviderError(
                provider="claude-4.5-haiku",
                original_error=str(e)
            )
    """

    def __init__(self, provider: str, original_error: str):
        super().__init__(
            message=f"LLM provider '{provider}' failed: {original_error}",
            error_code=ErrorCode.LLM_PROVIDER_ERROR,
            detail={"provider": provider, "error": original_error},
        )


class AllProvidersFailedError(InternalServerException):
    """모든 프로바이더 fallback 실패

    티어에 정의된 모든 fallback 모델이 실패했을 때 발생하는 예외입니다.
    이 경우 사용자에게 에러 응답을 반환해야 합니다.

    Example:
        attempted = ["claude-4.5-haiku", "gpt-4.1-mini", "gemini-2.0-flash"]
        raise AllProvidersFailedError(tier="light", attempts=attempted)
    """

    def __init__(self, tier: str, attempts: list[str]):
        super().__init__(
            message=f"All providers failed for tier '{tier}'",
            error_code=ErrorCode.ALL_PROVIDERS_FAILED,
            detail={"tier": tier, "attempted_models": attempts},
        )
