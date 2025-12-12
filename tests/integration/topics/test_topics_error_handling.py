# LLM API 호출 테스트 - 주석처리됨
# run_with_fallback에서 실제 API 호출 발생 방지

# """Topics 에러 처리 테스트
#
# 에이전트 실패, 스킵, LLM 오류 등 다양한 에러 시나리오 검증
# """
#
# import pytest
#
# from app.core.llm.types import AllProvidersFailedError
#
#
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_draft_api_with_llm_failure(
#     client, api_key_header, mock_llm_completion
# ):
#     """LLM 실패 시에도 200 응답 (500 아님)
#
#     AllProvidersFailedError 발생 시:
#     - 200 OK 응답
#     - warnings 필드에 에러 메시지 포함
#     - 에이전트는 SKIPPED 상태
#     """
#     # Mock LLM이 실패하도록 설정
#     mock_llm_completion.side_effect = AllProvidersFailedError(
#         tier="light", attempts=["model1", "model2"]
#     )
#
#     request_data = {
#         "user_id": 1,
#         "topic_id": 100,
#         "prompt": "Test with LLM failure",
#         "selected_contents": [],
#         "model_alias": "gpt-4o-mini",
#         "stream": False,
#     }
#
#     response = await client.post(
#         "/api/v1/topics/draft",
#         json=request_data,
#         headers=api_key_header,
#     )
#
#     # 200 응답 (500이 아님)
#     assert response.status_code == 200
#
#     data = response.json()["data"]
#
#     # warnings 필드 존재
#     if "warnings" in data:
#         assert len(data["warnings"]) > 0
#         # 경고 메시지에 "프로바이더" 또는 "실패" 포함
#         assert any(
#             "프로바이더" in w or "실패" in w for w in data["warnings"]
#         ), f"Expected warning about provider failure, got: {data['warnings']}"
#
#
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_draft_api_partial_agent_failure(
#     client, api_key_header, mock_llm_completion
# ):
#     """일부 에이전트만 실패해도 계속 진행
#
#     Summarizer 실패 → Writer는 실행됨
#     """
#     call_count = 0
#
#     async def conditional_mock(*args, **kwargs):
#         nonlocal call_count
#         call_count += 1
#
#         # 첫 번째 호출(summarizer)만 실패
#         if call_count == 1:
#             raise AllProvidersFailedError(tier="light", attempts=["model1"])
#
#         # 두 번째 호출(writer)은 성공
#         from app.core.llm.types import LLMResult
#
#         return LLMResult(
#             content="Mock draft content",
#             model="mock-model",
#             input_tokens=100,
#             output_tokens=50,
#             finish_reason="stop",
#         )
#
#     mock_llm_completion.side_effect = conditional_mock
#
#     request_data = {
#         "user_id": 1,
#         "topic_id": 100,
#         "prompt": "Test partial failure",
#         "selected_contents": [],
#         "model_alias": "gpt-4o-mini",
#         "stream": False,
#     }
#
#     response = await client.post(
#         "/api/v1/topics/draft",
#         json=request_data,
#         headers=api_key_header,
#     )
#
#     assert response.status_code == 200
#     data = response.json()["data"]
#
#     # Writer는 성공했으므로 draft_md 존재
#     assert "draft_md" in data
#
#     # Warnings 존재 (summarizer 실패)
#     if "warnings" in data:
#         assert len(data["warnings"]) > 0
#
#
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_draft_api_returns_warnings_in_response(client, api_key_header):
#     """경고 메시지가 응답에 포함되는지 확인"""
#     request_data = {
#         "user_id": 1,
#         "topic_id": 100,
#         "prompt": "Test",
#         "selected_contents": [],
#         "model_alias": "gpt-4o-mini",
#         "stream": False,
#     }
#
#     response = await client.post(
#         "/api/v1/topics/draft",
#         json=request_data,
#         headers=api_key_header,
#     )
#
#     assert response.status_code == 200
#     data = response.json()["data"]
#
#     # warnings 필드가 있으면 리스트여야 함
#     if "warnings" in data:
#         assert isinstance(data["warnings"], list)
#
#
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_draft_api_streaming_with_failure(
#     client, api_key_header, mock_llm_completion
# ):
#     """스트리밍 모드에서 LLM 실패 처리"""
#     mock_llm_completion.side_effect = AllProvidersFailedError(
#         tier="light", attempts=["model1"]
#     )
#
#     request_data = {
#         "user_id": 1,
#         "topic_id": 100,
#         "prompt": "Test streaming failure",
#         "selected_contents": [],
#         "model_alias": "gpt-4o-mini",
#         "stream": True,
#     }
#
#     response = await client.post(
#         "/api/v1/topics/draft",
#         json=request_data,
#         headers=api_key_header,
#     )
#
#     # SSE 스트림은 200 응답
#     assert response.status_code == 200
#
#     # 응답에 done 이벤트가 있어야 함
#     assert "event: done" in response.text
#
#
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_draft_api_with_invalid_topic_id(client, api_key_header):
#     """존재하지 않는 topic_id로 요청
#
#     현재는 validation만 하므로 200 OK
#     (DB 조회는 하지 않음)
#     """
#     request_data = {
#         "user_id": 1,
#         "topic_id": 999999,
#         "prompt": "Test",
#         "selected_contents": [],
#         "model_alias": "gpt-4o-mini",
#         "stream": False,
#     }
#
#     response = await client.post(
#         "/api/v1/topics/draft",
#         json=request_data,
#         headers=api_key_header,
#     )
#
#     # 현재는 validation만 하므로 200
#     # 향후 topic 존재 여부 확인 시 404로 변경 가능
#     assert response.status_code in [200, 404]
#
#
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_draft_api_with_malformed_content(client, api_key_header):
#     """잘못된 selected_contents 형식"""
#     request_data = {
#         "user_id": 1,
#         "topic_id": 100,
#         "prompt": "Test",
#         "selected_contents": [
#             {"invalid_field": "value"}  # content_id, title, summary 누락
#         ],
#         "model_alias": "gpt-4o-mini",
#         "stream": False,
#     }
#
#     response = await client.post(
#         "/api/v1/topics/draft",
#         json=request_data,
#         headers=api_key_header,
#     )
#
#     # 422 Validation Error 또는 200 (dict 형식이면 허용)
#     assert response.status_code in [200, 422]
#
#
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_draft_api_timeout_handling(client, api_key_header):
#     """API 타임아웃 처리 (장시간 실행)
#
#     실제로는 timeout이 설정되어 있어야 하지만,
#     mock 환경에서는 빠르게 응답
#     """
#     request_data = {
#         "user_id": 1,
#         "topic_id": 100,
#         "prompt": "Test timeout",
#         "selected_contents": [],
#         "model_alias": "gpt-4o-mini",
#         "stream": False,
#     }
#
#     response = await client.post(
#         "/api/v1/topics/draft",
#         json=request_data,
#         headers=api_key_header,
#     )
#
#     # Mock 환경에서는 빠르게 응답
#     assert response.status_code == 200
#
#
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_draft_api_concurrent_requests(client, api_key_header):
#     """동시 요청 처리 가능 여부
#
#     동시에 여러 draft 요청을 보내도 정상 처리
#     """
#     import asyncio
#
#     request_data = {
#         "user_id": 1,
#         "topic_id": 100,
#         "prompt": "Concurrent test",
#         "selected_contents": [],
#         "model_alias": "gpt-4o-mini",
#         "stream": False,
#     }
#
#     # 3개 동시 요청
#     tasks = [
#         client.post(
#             "/api/v1/topics/draft", json=request_data, headers=api_key_header
#         )
#         for _ in range(3)
#     ]
#
#     responses = await asyncio.gather(*tasks)
#
#     # 모두 성공
#     for response in responses:
#         assert response.status_code == 200
#         data = response.json()["data"]
#         assert "title" in data
#         assert "draft_md" in data
