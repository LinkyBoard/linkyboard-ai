# LLM API 호출 테스트 - 주석처리됨
# run_with_fallback에서 실제 API 호출 발생 방지

# """Topics Draft API 통합 테스트
# 
# API 레벨에서 전체 플로우 검증
# """
# 
# import pytest
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_draft_api_success_non_streaming(client, api_key_header):
#     """Draft API 전체 플로우 검증 (non-streaming)
# 
#     검증 항목:
#     - API 응답 구조
#     - title, draft_md 생성
#     - usage 계산 (토큰, WTU)
#     - 에이전트별 사용량
#     """
#     request_data = {
#         "user_id": 1,
#         "topic_id": 100,
#         "prompt": "Write about Python async programming",
#         "selected_contents": [
#             {
#                 "content_id": 1,
#                 "title": "Asyncio Basics",
#                 "summary": "Introduction to asyncio in Python",
#             },
#             {
#                 "content_id": 2,
#                 "title": "Python Concurrency",
#                 "summary": "Concurrency patterns in Python",
#             },
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
#     assert response.status_code == 200
# 
#     response_data = response.json()
#     assert response_data["success"] is True
#     assert "data" in response_data
# 
#     data = response_data["data"]
# 
#     # 기본 필드 검증
#     assert "title" in data
#     assert "draft_md" in data
#     assert "usage" in data
# 
#     # Title 생성 확인
#     assert isinstance(data["title"], str)
#     assert len(data["title"]) > 0
# 
#     # Draft 생성 확인
#     assert isinstance(data["draft_md"], str)
#     assert len(data["draft_md"]) > 0
# 
#     # Usage 구조 검증
#     usage = data["usage"]
#     assert "total_input_tokens" in usage
#     assert "total_output_tokens" in usage
#     assert "total_wtu" in usage
#     assert "agents" in usage
# 
#     # 토큰 수가 0보다 큼
#     assert usage["total_input_tokens"] > 0
#     assert usage["total_output_tokens"] > 0
#     assert usage["total_wtu"] > 0
# 
#     # 에이전트별 사용량 존재
#     assert "summarizer" in usage["agents"]
#     assert "writer" in usage["agents"]
# 
#     # 각 에이전트 사용량 구조
#     for agent_name in ["summarizer", "writer"]:
#         agent_usage = usage["agents"][agent_name]
#         assert "model" in agent_usage
#         assert "input_tokens" in agent_usage
#         assert "output_tokens" in agent_usage
#         assert "wtu" in agent_usage
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_draft_api_usage_calculation(client, api_key_header):
#     """Usage 계산 정확성 검증
# 
#     Mock LLM이 반환하는 토큰 수가 usage에 정확히 반영되는지 확인
#     """
#     request_data = {
#         "user_id": 1,
#         "topic_id": 100,
#         "prompt": "Test prompt",
#         "selected_contents": [
#             {"content_id": 1, "title": "Content 1", "summary": "Summary 1"}
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
#     assert response.status_code == 200
#     data = response.json()["data"]
#     usage = data["usage"]
# 
#     # Mock LLM은 각 호출마다 input=100, output=50 반환
#     # summarizer: 100 + 50 = 150
#     # writer: 100 + 50 = 150
#     # total: 300 tokens
#     # WTU: 각 에이전트 1 (최소값) = 총 2
# 
#     assert usage["total_input_tokens"] == 200  # 100 * 2
#     assert usage["total_output_tokens"] == 100  # 50 * 2
#     assert usage["total_wtu"] == 2  # 각 에이전트 최소 1 WTU
# 
#     # 에이전트별 확인
#     assert usage["agents"]["summarizer"]["input_tokens"] == 100
#     assert usage["agents"]["summarizer"]["output_tokens"] == 50
#     assert usage["agents"]["summarizer"]["wtu"] == 1
# 
#     assert usage["agents"]["writer"]["input_tokens"] == 100
#     assert usage["agents"]["writer"]["output_tokens"] == 50
#     assert usage["agents"]["writer"]["wtu"] == 1
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_draft_api_requires_authentication(client):
#     """API 인증 필수 확인
# 
#     Note: FastAPI validation이 authentication보다 먼저 실행되므로,
#     API Key가 없어도 validation error가 발생할 수 있음.
#     실제 production에서는 인증 middleware가 먼저 체크함.
#     """
#     request_data = {
#         "user_id": 1,
#         "topic_id": 100,
#         "prompt": "Test",
#         "selected_contents": [],
#         "model_alias": "gpt-4o-mini",
#         "stream": False,
#     }
# 
#     # X-Internal-Api-Key 없이 요청
#     response = await client.post("/api/v1/topics/draft", json=request_data)
# 
#     # 401, 403 (인증 실패) 또는 422 (validation error, FastAPI 동작)
#     assert response.status_code in [401, 403, 422]
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_draft_api_with_empty_contents(client, api_key_header):
#     """선택된 콘텐츠가 없어도 동작"""
#     request_data = {
#         "user_id": 1,
#         "topic_id": 100,
#         "prompt": "Write about general programming concepts",
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
#     # 콘텐츠 없어도 title, draft_md 생성됨
#     assert len(data["title"]) > 0
#     assert len(data["draft_md"]) > 0
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_draft_api_with_retrieval_mode(client, api_key_header):
#     """RetrievalMode 파라미터 검증
# 
#     Note: Draft API는 retrieval_mode를 지원하지 않음 (Ask API만 지원)
#     """
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
#     assert "title" in data
#     assert "draft_md" in data
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_draft_api_invalid_request(client, api_key_header):
#     """잘못된 요청 검증"""
#     # 필수 필드 누락 (user_id)
#     request_data = {
#         "topic_id": 100,
#         "prompt": "Test",
#         "selected_contents": [],
#     }
# 
#     response = await client.post(
#         "/api/v1/topics/draft",
#         json=request_data,
#         headers=api_key_header,
#     )
# 
#     # 422 Validation Error
#     assert response.status_code == 422
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_draft_api_response_structure(client, api_key_header):
#     """API 응답 구조 상세 검증"""
#     request_data = {
#         "user_id": 1,
#         "topic_id": 100,
#         "prompt": "Test prompt",
#         "selected_contents": [
#             {"content_id": 1, "title": "Test", "summary": "Summary"}
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
#     assert response.status_code == 200
#     response_json = response.json()
# 
#     # 최상위 구조
#     assert "success" in response_json
#     assert "data" in response_json
#     assert response_json["success"] is True
# 
#     data = response_json["data"]
# 
#     # 필수 필드 존재
#     required_fields = ["title", "draft_md", "usage"]
#     for field in required_fields:
#         assert field in data, f"Missing required field: {field}"
# 
#     # Usage 상세 구조
#     usage = data["usage"]
#     usage_fields = [
#         "total_input_tokens",
#         "total_output_tokens",
#         "total_wtu",
#         "agents",
#     ]
#     for field in usage_fields:
#         assert field in usage, f"Missing usage field: {field}"
# 
#     # Agents 구조
#     assert isinstance(usage["agents"], dict)
#     assert len(usage["agents"]) > 0
# 
#     # 각 agent 사용량 구조
#     for _agent_name, agent_usage in usage["agents"].items():
#         assert "model" in agent_usage
#         assert "input_tokens" in agent_usage
#         assert "output_tokens" in agent_usage
#         assert "wtu" in agent_usage
# 
#         # 타입 검증
#         assert isinstance(agent_usage["input_tokens"], int)
#         assert isinstance(agent_usage["output_tokens"], int)
#         assert isinstance(agent_usage["wtu"], int)
