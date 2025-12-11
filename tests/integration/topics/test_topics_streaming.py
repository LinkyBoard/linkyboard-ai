"""Topics SSE 스트리밍 테스트

SSE 이벤트 순서 및 구조 검증
"""

import json

import pytest


def parse_sse_events(response_text: str) -> list[dict]:
    """SSE 텍스트를 이벤트 리스트로 파싱"""
    events = []
    current_event: dict[str, str | dict] = {}

    for line in response_text.strip().split("\n"):
        line = line.strip()
        if not line:
            if current_event:
                events.append(current_event)
                current_event = {}
            continue

        if line.startswith("event:"):
            current_event["event"] = line[6:].strip()
        elif line.startswith("data:"):
            try:
                current_event["data"] = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                current_event["data"] = line[5:].strip()

    # 마지막 이벤트 추가
    if current_event:
        events.append(current_event)

    return events


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_draft_api_streaming_events(client, api_key_header):
    """SSE 스트리밍 이벤트 순서 검증

    예상 순서:
    1. plan - 실행 계획
    2. status - Stage 시작
    3. agent_start - 에이전트 시작
    4. agent_done - 에이전트 완료
    5. (반복)
    6. done - 최종 완료
    """
    request_data = {
        "user_id": 1,
        "topic_id": 100,
        "prompt": "Test streaming",
        "selected_contents": [
            {"content_id": 1, "title": "Test", "summary": "Summary"}
        ],
        "model_alias": "gpt-4o-mini",
        "stream": True,
        "verbose": True,  # verbose=True일 때만 plan, status 이벤트 발생
    }

    response = await client.post(
        "/api/v1/topics/draft",
        json=request_data,
        headers=api_key_header,
    )

    assert response.status_code == 200
    assert (
        response.headers["content-type"] == "text/event-stream; charset=utf-8"
    )

    # SSE 응답 파싱
    events = parse_sse_events(response.text)

    # 최소 이벤트 수 확인
    assert len(events) > 0

    # 이벤트 타입 추출
    event_types = [e.get("event") for e in events]

    # plan 이벤트 존재 (verbose=True)
    assert "plan" in event_types

    # status 이벤트 존재 (각 Stage마다)
    assert "status" in event_types

    # agent_start, agent_done 이벤트 존재
    assert "agent_start" in event_types
    assert "agent_done" in event_types

    # done 이벤트가 마지막
    assert events[-1]["event"] == "done"

    # agent_start와 agent_done 쌍이 맞는지 확인
    start_count = event_types.count("agent_start")
    done_count = event_types.count("agent_done")
    assert start_count == done_count
    assert start_count >= 2  # summarizer + writer


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_streaming_plan_event_structure(client, api_key_header):
    """plan 이벤트 구조 검증"""
    request_data = {
        "user_id": 1,
        "topic_id": 100,
        "prompt": "Test",
        "selected_contents": [],
        "model_alias": "gpt-4o-mini",
        "stream": True,
        "verbose": True,
    }

    response = await client.post(
        "/api/v1/topics/draft",
        json=request_data,
        headers=api_key_header,
    )

    events = parse_sse_events(response.text)
    plan_events = [e for e in events if e.get("event") == "plan"]

    assert len(plan_events) > 0

    plan_data = plan_events[0]["data"]

    # plan 이벤트 필드
    assert "plan_id" in plan_data
    assert "retrieval_mode" in plan_data
    assert "stages" in plan_data

    # stages 구조
    assert isinstance(plan_data["stages"], list)
    assert len(plan_data["stages"]) >= 2  # summarizer, writer

    # 각 stage 구조
    for stage in plan_data["stages"]:
        assert "index" in stage
        assert "parallel" in stage
        assert "agents" in stage

        # agents 구조
        for agent_spec in stage["agents"]:
            assert "agent" in agent_spec
            assert "reason" in agent_spec


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_streaming_status_event_structure(client, api_key_header):
    """status 이벤트 구조 검증"""
    request_data = {
        "user_id": 1,
        "topic_id": 100,
        "prompt": "Test",
        "selected_contents": [],
        "model_alias": "gpt-4o-mini",
        "stream": True,
        "verbose": True,
    }

    response = await client.post(
        "/api/v1/topics/draft",
        json=request_data,
        headers=api_key_header,
    )

    events = parse_sse_events(response.text)
    status_events = [e for e in events if e.get("event") == "status"]

    assert len(status_events) >= 2  # Stage 1, Stage 2

    for status_event in status_events:
        data = status_event["data"]
        assert "stage" in data
        assert "parallel" in data
        assert "agents" in data

        # stage는 1부터 시작
        assert data["stage"] >= 1
        assert isinstance(data["agents"], list)


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_streaming_agent_events_structure(client, api_key_header):
    """agent_start, agent_done 이벤트 구조 검증"""
    request_data = {
        "user_id": 1,
        "topic_id": 100,
        "prompt": "Test",
        "selected_contents": [],
        "model_alias": "gpt-4o-mini",
        "stream": True,
        "verbose": True,
    }

    response = await client.post(
        "/api/v1/topics/draft",
        json=request_data,
        headers=api_key_header,
    )

    events = parse_sse_events(response.text)

    # agent_start 이벤트
    start_events = [e for e in events if e.get("event") == "agent_start"]
    assert len(start_events) >= 2

    for event in start_events:
        data = event["data"]
        assert "agent" in data
        assert "stage" in data
        assert data["agent"] in ["summarizer", "writer"]

    # agent_done 이벤트
    done_events = [e for e in events if e.get("event") == "agent_done"]
    assert len(done_events) >= 2

    for event in done_events:
        data = event["data"]
        assert "agent" in data
        assert "stage" in data
        assert "success" in data
        assert "skipped" in data


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_streaming_done_event(client, api_key_header):
    """done 이벤트에 최종 응답 포함 확인"""
    request_data = {
        "user_id": 1,
        "topic_id": 100,
        "prompt": "Test",
        "selected_contents": [],
        "model_alias": "gpt-4o-mini",
        "stream": True,
    }

    response = await client.post(
        "/api/v1/topics/draft",
        json=request_data,
        headers=api_key_header,
    )

    events = parse_sse_events(response.text)
    done_events = [e for e in events if e.get("event") == "done"]

    assert len(done_events) == 1

    done_data = done_events[0]["data"]

    # done 이벤트 구조: {success: True, data: {...}}
    assert "success" in done_data
    assert "data" in done_data
    assert done_data["success"] is True

    # data 내부에 complete response 포함
    data = done_data["data"]
    assert "title" in data
    assert "draft_md" in data
    assert "usage" in data

    # Usage 구조
    usage = data["usage"]
    assert "total_input_tokens" in usage
    assert "total_output_tokens" in usage
    assert "total_wtu" in usage
    assert "agents" in usage


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_streaming_non_verbose_mode(client, api_key_header):
    """verbose=False 모드에서는 일부 이벤트 필터링

    Note: 실제 구현에서는 verbose=False여도 기본 이벤트는 발생할 수 있음.
    verbose는 추가적인 상세 정보 제공 여부를 결정.
    """
    request_data = {
        "user_id": 1,
        "topic_id": 100,
        "prompt": "Test",
        "selected_contents": [],
        "model_alias": "gpt-4o-mini",
        "stream": True,
        "verbose": False,
    }

    response = await client.post(
        "/api/v1/topics/draft",
        json=request_data,
        headers=api_key_header,
    )

    events = parse_sse_events(response.text)
    event_types = [e.get("event") for e in events]

    # 필수 이벤트는 항상 있어야 함
    assert "agent_start" in event_types
    assert "agent_done" in event_types
    assert "done" in event_types

    # done 이벤트가 마지막
    assert event_types[-1] == "done"


@pytest.mark.asyncio
@pytest.mark.mock_ai
async def test_streaming_event_order(client, api_key_header):
    """이벤트 순서 검증 (verbose=True)"""
    request_data = {
        "user_id": 1,
        "topic_id": 100,
        "prompt": "Test",
        "selected_contents": [],
        "model_alias": "gpt-4o-mini",
        "stream": True,
        "verbose": True,
    }

    response = await client.post(
        "/api/v1/topics/draft",
        json=request_data,
        headers=api_key_header,
    )

    events = parse_sse_events(response.text)
    event_types = [e.get("event") for e in events]

    # plan이 첫 번째여야 함
    assert event_types[0] == "plan"

    # done이 마지막이어야 함
    assert event_types[-1] == "done"

    # agent_start 다음에 agent_done이 와야 함
    for i, event_type in enumerate(event_types):
        if event_type == "agent_start":
            # 같은 agent의 done을 찾음
            agent_name = events[i]["data"]["agent"]
            found_done = False
            for j in range(i + 1, len(events)):
                if (
                    event_types[j] == "agent_done"
                    and events[j]["data"]["agent"] == agent_name
                ):
                    found_done = True
                    break
            assert found_done, f"agent_done not found for {agent_name}"
