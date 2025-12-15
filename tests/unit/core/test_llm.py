"""Core LLM 모듈 단위 테스트"""

from unittest.mock import MagicMock, patch

import pytest

from app.core.llm.fallback import call_with_fallback, create_embedding
from app.core.llm.provider import acompletion_raw
from app.core.llm.types import (
    AllProvidersFailedError,
    LLMMessage,
    LLMProviderError,
    LLMResult,
    LLMTier,
)


@pytest.mark.asyncio
async def test_acompletion_raw_success():
    """LiteLLM completion 성공 시나리오"""
    with patch("app.core.llm.provider.acompletion") as mock_completion:
        # Mock 응답 구성
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "claude-4.5-haiku"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_completion.return_value = mock_response

        # 실행
        result = await acompletion_raw(
            model="claude-4.5-haiku",
            messages=[LLMMessage(role="user", content="Hello")],
        )

        # 검증
        assert result.content == "Test response"
        assert result.model == "claude-4.5-haiku"
        assert result.input_tokens == 10
        assert result.output_tokens == 20


@pytest.mark.asyncio
async def test_acompletion_raw_failure():
    """LiteLLM completion 실패 시나리오"""
    with patch("app.core.llm.provider.acompletion") as mock_completion:
        mock_completion.side_effect = Exception("API error")

        with pytest.raises(LLMProviderError) as exc_info:
            await acompletion_raw(
                model="claude-4.5-haiku",
                messages=[LLMMessage(role="user", content="Hello")],
            )

        assert "API error" in str(exc_info.value.detail_info["error"])


@pytest.mark.asyncio
async def test_call_with_fallback_first_success():
    """Fallback: 첫 번째 모델 성공"""
    with patch("app.core.llm.fallback.acompletion_raw") as mock_completion:
        mock_completion.return_value = LLMResult(
            content="Success",
            model="claude-4.5-haiku",
            input_tokens=10,
            output_tokens=20,
        )

        result = await call_with_fallback(
            tier=LLMTier.LIGHT,
            messages=[LLMMessage(role="user", content="Test")],
        )

        assert result.content == "Success"
        assert result.model == "claude-4.5-haiku"
        # 첫 번째 모델만 호출되었는지 확인
        assert mock_completion.call_count == 1


@pytest.mark.asyncio
async def test_call_with_fallback_second_success():
    """Fallback: 첫 번째 실패, 두 번째 성공"""
    with patch("app.core.llm.fallback.acompletion_raw") as mock_completion:
        # 첫 번째 호출 실패, 두 번째 호출 성공
        mock_completion.side_effect = [
            LLMProviderError(
                provider="claude-4.5-haiku", original_error="Rate limit"
            ),
            LLMResult(
                content="Success from fallback",
                model="gpt-4.1-mini",
                input_tokens=10,
                output_tokens=20,
            ),
        ]

        result = await call_with_fallback(
            tier=LLMTier.LIGHT,
            messages=[LLMMessage(role="user", content="Test")],
        )

        assert result.content == "Success from fallback"
        assert result.model == "gpt-4.1-mini"
        assert mock_completion.call_count == 2


@pytest.mark.asyncio
async def test_call_with_fallback_all_fail():
    """Fallback: 모든 모델 실패"""
    with patch("app.core.llm.fallback.acompletion_raw") as mock_completion:
        mock_completion.side_effect = LLMProviderError(
            provider="test", original_error="error"
        )

        with pytest.raises(AllProvidersFailedError) as exc_info:
            await call_with_fallback(
                tier=LLMTier.LIGHT,
                messages=[LLMMessage(role="user", content="Test")],
            )

        assert "light" in str(exc_info.value.detail_info["tier"])


@pytest.mark.asyncio
async def test_create_embedding_success():
    """임베딩 생성 성공"""
    with patch("app.core.llm.fallback.aembedding_raw") as mock_embedding:
        mock_embedding.return_value = [0.1, 0.2, 0.3]

        result = await create_embedding("Test text")

        assert result == [0.1, 0.2, 0.3]
        assert mock_embedding.call_count == 1


@pytest.mark.asyncio
async def test_create_embedding_no_fallback():
    """임베딩 실패 시 fallback 없이 예외 발생"""
    with patch("app.core.llm.fallback.aembedding_raw") as mock_embedding:
        mock_embedding.side_effect = LLMProviderError(
            provider="text-embedding-3-large", original_error="API error"
        )

        with pytest.raises(LLMProviderError):
            await create_embedding("Test text")
