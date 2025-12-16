# """Core LLM 스트리밍 테스트"""
#
# # LLM API 호출 테스트 - 주석처리됨
# # run_with_fallback에서 실제 API 호출 발생 방지
#
# # from unittest.mock import patch
#
# # import pytest
#
# # from app.core.llm.fallback import stream_with_fallback
# # from app.core.llm.types import (
# #     AllProvidersFailedError,
# #     LLMMessage,
# #     LLMProviderError,
# #     LLMTier,
# # )
#
#
# # @pytest.mark.asyncio
# # async def test_stream_with_fallback_success():
# #     """스트리밍 성공 테스트"""
# #     with patch("app.core.llm.fallback.astream_completion_raw") as mock_stream:
#
# #         async def mock_chunks():
# #             yield "Hello"
# #             yield " "
# #             yield "World"
#
# #         mock_stream.return_value = mock_chunks()
#
# #         chunks = []
# #         async for chunk in stream_with_fallback(
# #             tier=LLMTier.LIGHT,
# #             messages=[LLMMessage(role="user", content="Test")],
# #         ):
# #             chunks.append(chunk)
#
# #         assert chunks == ["Hello", " ", "World"]
# #         # 첫 번째 모델만 호출되었는지 확인
# #         assert mock_stream.call_count == 1
#
#
# # @pytest.mark.asyncio
# # async def test_stream_fallback_before_streaming():
# #     """스트리밍 시작 전 에러: fallback 시도"""
# #     with patch("app.core.llm.fallback.astream_completion_raw") as mock_stream:
# #         # 첫 번째 모델 실패 (스트리밍 시작 전)
# #         # 두 번째 모델 성공
#
# #         async def first_model_fail():
# #             raise LLMProviderError(
# #                 provider="claude-4.5-haiku", original_error="Connection error"
# #             )
# #             # yield가 없으므로 스트리밍 시작되지 않음
# #             yield  # unreachable
#
# #         async def second_model_success():
# #             yield "Success"
# #             yield " from"
# #             yield " fallback"
#
# #         mock_stream.side_effect = [
# #             first_model_fail(),
# #             second_model_success(),
# #         ]
#
# #         chunks = []
# #         async for chunk in stream_with_fallback(
# #             tier=LLMTier.LIGHT,
# #             messages=[LLMMessage(role="user", content="Test")],
# #         ):
# #             chunks.append(chunk)
#
# #         # 두 모델이 시도됨
# #         assert mock_stream.call_count == 2
# #         # 두 번째 모델의 응답만 반환됨
# #         assert chunks == ["Success", " from", " fallback"]
#
#
# # @pytest.mark.asyncio
# # async def test_stream_no_fallback_mid_stream():
# #     """스트리밍 중 에러: fallback 없이 즉시 에러 발생"""
# #     with patch("app.core.llm.fallback.astream_completion_raw") as mock_stream:
#
# #         async def fail_mid_stream():
# #             yield "Hello"  # 첫 번째 청크 성공
# #             yield " "  # 두 번째 청크 성공
# #             # 세 번째 청크에서 에러 발생
# #             raise LLMProviderError(
# #                 provider="claude-4.5-haiku",
# #                 original_error="Stream interrupted",
# #             )
#
# #         mock_stream.return_value = fail_mid_stream()
#
# #         chunks = []
# #         with pytest.raises(LLMProviderError) as exc_info:
# #             async for chunk in stream_with_fallback(
# #                 tier=LLMTier.LIGHT,
# #                 messages=[LLMMessage(role="user", content="Test")],
# #             ):
# #                 chunks.append(chunk)
#
# #         # 첫 번째 모델만 시도 (fallback 없음)
# #         assert mock_stream.call_count == 1
# #         # 에러 전까지 받은 청크들
# #         assert chunks == ["Hello", " "]
# #         assert "claude-4.5-haiku" in str(
# #             exc_info.value.detail_info["provider"]
# #         )
#
#
# # @pytest.mark.asyncio
# # async def test_stream_all_providers_failed():
# #     """모든 모델이 스트리밍 시작 전에 실패"""
# #     with patch("app.core.llm.fallback.astream_completion_raw") as mock_stream:
# #         # LIGHT 티어의 모든 모델 (3개)이 스트리밍 시작 전 실패
# #         mock_stream.side_effect = LLMProviderError(
# #             provider="test", original_error="Connection error"
# #         )
#
# #         with pytest.raises(AllProvidersFailedError) as exc_info:
# #             async for _ in stream_with_fallback(
# #                 tier=LLMTier.LIGHT,
# #                 messages=[LLMMessage(role="user", content="Test")],
# #             ):
# #                 pass
#
# #         # 3개 모델 모두 시도됨
# #         assert mock_stream.call_count == 3
# #         assert "light" in str(exc_info.value.detail_info["tier"])
