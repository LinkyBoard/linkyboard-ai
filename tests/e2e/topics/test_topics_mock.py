# LLM API 호출 테스트 - 주석처리됨
# run_with_fallback에서 실제 API 호출 발생 방지

# """Topics E2E Tests - Mock AI
# 
# 전체 플로우 검증 (Orchestrator → Executor → Agents → API Response)
# Mock LLM으로 빠른 실행, CI/CD에서 자동 실행
# """
# 
# import pytest
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_e2e_draft_creation_full_flow(client, api_key_header):
#     """E2E: Draft 생성 전체 플로우
# 
#     검증 항목:
#     - Request → Orchestrator → Executor → Agents → Response
#     - Summarizer → Writer 순차 실행
#     - Context 누적 (Stage 1 → Stage 2)
#     - Title 추출 (마크다운 헤더에서)
#     - Usage/WTU 계산
#     """
#     request_data = {
#         "user_id": 1,
#         "topic_id": 100,
#         "prompt": "Write a comprehensive guide about Python async programming",
#         "selected_contents": [
#             {
#                 "content_id": 1,
#                 "title": "Asyncio Basics",
#                 "summary": "Introduction to asyncio library in Python",
#             },
#             {
#                 "content_id": 2,
#                 "title": "Async/Await Pattern",
#                 "summary": "Understanding async/await syntax and coroutines",
#             },
#         ],
#         "model_alias": "gpt-4o-mini",
#         "stream": False,
#         "verbose": False,
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
#     assert response_json["success"] is True
#     assert "data" in response_json
# 
#     data = response_json["data"]
# 
#     # 핵심 출력 검증
#     assert "title" in data
#     assert "draft_md" in data
#     assert "usage" in data
# 
#     # Title 생성 확인 (Mock LLM 출력 기반)
#     assert isinstance(data["title"], str)
#     assert len(data["title"]) > 0
# 
#     # Draft 생성 확인
#     assert isinstance(data["draft_md"], str)
#     assert len(data["draft_md"]) > 0  # Mock 출력 확인
# 
#     # Usage 계산 확인 (Mock LLM: 각 에이전트 100 input + 50 output)
#     usage = data["usage"]
#     assert usage["total_input_tokens"] == 200  # summarizer(100) + writer(100)
#     assert usage["total_output_tokens"] == 100  # summarizer(50) + writer(50)
#     assert usage["total_wtu"] >= 2  # 각 에이전트 최소 1 WTU
# 
#     # 에이전트별 사용량
#     assert "summarizer" in usage["agents"]
#     assert "writer" in usage["agents"]
# 
#     summarizer_usage = usage["agents"]["summarizer"]
#     assert summarizer_usage["input_tokens"] == 100
#     assert summarizer_usage["output_tokens"] == 50
#     assert summarizer_usage["wtu"] >= 1
# 
#     writer_usage = usage["agents"]["writer"]
#     assert writer_usage["input_tokens"] == 100
#     assert writer_usage["output_tokens"] == 50
#     assert writer_usage["wtu"] >= 1
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_e2e_draft_with_empty_contents(client, api_key_header):
#     """E2E: 선택 콘텐츠 없이 Draft 생성
# 
#     검증:
#     - 콘텐츠 없어도 정상 동작
#     - Writer가 프롬프트만으로 초안 작성
#     """
#     request_data = {
#         "user_id": 1,
#         "topic_id": 100,
#         "prompt": "Write about the importance of code documentation",
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
#     # Usage 계산 (summarizer는 스킵되거나 빈 출력, writer만 실행)
#     usage = data["usage"]
#     assert usage["total_input_tokens"] > 0
#     assert usage["total_output_tokens"] > 0
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_e2e_streaming_full_flow(client, api_key_header):
#     """E2E: 스트리밍 모드 전체 플로우
# 
#     검증:
#     - SSE 이벤트 순서
#     - 각 이벤트 데이터 구조
#     - 최종 done 이벤트에 complete response
#     """
#     request_data = {
#         "user_id": 1,
#         "topic_id": 100,
#         "prompt": "Write about REST API design principles",
#         "selected_contents": [
#             {
#                 "content_id": 1,
#                 "title": "REST Basics",
#                 "summary": "RESTful architecture fundamentals",
#             }
#         ],
#         "model_alias": "gpt-4o-mini",
#         "stream": True,
#         "verbose": True,
#     }
# 
#     response = await client.post(
#         "/api/v1/topics/draft",
#         json=request_data,
#         headers=api_key_header,
#     )
# 
#     assert response.status_code == 200
#     assert (
#         response.headers["content-type"] == "text/event-stream; charset=utf-8"
#     )
# 
#     # SSE 응답에 필수 이벤트 포함 확인
#     response_text = response.text
#     assert "event: plan" in response_text  # verbose=True
#     assert "event: status" in response_text
#     assert "event: agent_start" in response_text
#     assert "event: agent_done" in response_text
#     assert "event: done" in response_text
# 
#     # done 이벤트가 마지막
#     lines = response_text.strip().split("\n")
#     last_event_line = None
#     for line in reversed(lines):
#         if line.startswith("event:"):
#             last_event_line = line
#             break
#     assert last_event_line == "event: done"
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_e2e_draft_with_multiple_contents(client, api_key_header):
#     """E2E: 다수의 콘텐츠로 Draft 생성
# 
#     검증:
#     - 여러 콘텐츠 처리
#     - Summarizer가 모든 콘텐츠 요약
#     - Writer가 통합된 초안 작성
#     """
#     request_data = {
#         "user_id": 1,
#         "topic_id": 100,
#         "prompt": "Create a guide combining these programming concepts",
#         "selected_contents": [
#             {
#                 "content_id": 1,
#                 "title": "OOP Principles",
#                 "summary": "Object-oriented programming fundamentals",
#             },
#             {
#                 "content_id": 2,
#                 "title": "Functional Programming",
#                 "summary": "Functional programming paradigms",
#             },
#             {
#                 "content_id": 3,
#                 "title": "Design Patterns",
#                 "summary": "Common software design patterns",
#             },
#             {
#                 "content_id": 4,
#                 "title": "SOLID Principles",
#                 "summary": "Five principles for maintainable code",
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
#     data = response.json()["data"]
# 
#     # 다수 콘텐츠 처리 확인
#     assert len(data["title"]) > 0
#     assert len(data["draft_md"]) > 0
# 
#     # Usage 계산 (4개 콘텐츠 처리)
#     usage = data["usage"]
#     assert usage["total_input_tokens"] > 0
#     assert usage["total_output_tokens"] > 0
# 
#     # Summarizer와 Writer 모두 실행
#     assert "summarizer" in usage["agents"]
#     assert "writer" in usage["agents"]
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_e2e_draft_response_completeness(client, api_key_header):
#     """E2E: 응답 완전성 검증
# 
#     검증:
#     - 모든 필수 필드 존재
#     - 데이터 타입 정확성
#     - 중첩 구조 완전성
#     """
#     request_data = {
#         "user_id": 999,
#         "topic_id": 888,
#         "prompt": "Write about software testing best practices",
#         "selected_contents": [
#             {
#                 "content_id": 10,
#                 "title": "Unit Testing",
#                 "summary": "Writing effective unit tests",
#             }
#         ],
#         "model_alias": "gpt-4o-mini",
#         "stream": False,
#         "verbose": False,
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
#     assert isinstance(response_json["success"], bool)
#     assert isinstance(response_json["data"], dict)
# 
#     data = response_json["data"]
# 
#     # 필수 필드
#     required_fields = ["title", "draft_md", "usage"]
#     for field in required_fields:
#         assert field in data, f"Missing required field: {field}"
#         assert data[field] is not None, f"Field {field} is None"
# 
#     # 타입 검증
#     assert isinstance(data["title"], str)
#     assert isinstance(data["draft_md"], str)
#     assert isinstance(data["usage"], dict)
# 
#     # Usage 구조
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
#     assert isinstance(usage["total_input_tokens"], int)
#     assert isinstance(usage["total_output_tokens"], int)
#     assert isinstance(usage["total_wtu"], int)
#     assert isinstance(usage["agents"], dict)
# 
#     # Agents 구조
#     for agent_name, agent_usage in usage["agents"].items():
#         assert isinstance(agent_name, str)
#         assert isinstance(agent_usage, dict)
#         assert "model" in agent_usage
#         assert "input_tokens" in agent_usage
#         assert "output_tokens" in agent_usage
#         assert "wtu" in agent_usage
# 
# 
# @pytest.mark.asyncio
# @pytest.mark.mock_ai
# async def test_e2e_draft_with_verbose_mode(client, api_key_header):
#     """E2E: Verbose 모드 비교
# 
#     검증:
#     - verbose=True: 상세 정보 포함 (스트리밍만 해당)
#     - verbose=False: 기본 정보만
#     - 기능은 동일하게 동작
#     """
#     # verbose=False (기본)
#     request_non_verbose = {
#         "user_id": 1,
#         "topic_id": 100,
#         "prompt": "Write about database indexing",
#         "selected_contents": [
#             {"content_id": 1, "title": "DB Indexes", "summary": "Index basics"}
#         ],
#         "model_alias": "gpt-4o-mini",
#         "stream": False,
#         "verbose": False,
#     }
# 
#     response_non_verbose = await client.post(
#         "/api/v1/topics/draft",
#         json=request_non_verbose,
#         headers=api_key_header,
#     )
# 
#     # verbose=True
#     request_verbose = {
#         **request_non_verbose,
#         "verbose": True,
#     }
# 
#     response_verbose = await client.post(
#         "/api/v1/topics/draft",
#         json=request_verbose,
#         headers=api_key_header,
#     )
# 
#     # 둘 다 성공
#     assert response_non_verbose.status_code == 200
#     assert response_verbose.status_code == 200
# 
#     data_non_verbose = response_non_verbose.json()["data"]
#     data_verbose = response_verbose.json()["data"]
# 
#     # 기본 출력은 동일 (title, draft_md, usage)
#     assert "title" in data_non_verbose
#     assert "title" in data_verbose
#     assert "draft_md" in data_non_verbose
#     assert "draft_md" in data_verbose
#     assert "usage" in data_non_verbose
#     assert "usage" in data_verbose
# 
#     # verbose는 스트리밍에서만 차이 (non-streaming은 동일)
#     # 여기서는 둘 다 동일한 구조 확인
#     assert data_non_verbose.keys() == data_verbose.keys()
