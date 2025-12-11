"""Topics E2E Tests - Real AI

실제 LLM API 호출 테스트 (비용 발생)
수동 실행: ENABLE_REAL_AI_TESTS=true pytest -m real_ai
"""

import os

import pytest

# Real AI 테스트 스킵 조건
skip_if_no_real_ai = pytest.mark.skipif(
    os.getenv("ENABLE_REAL_AI_TESTS", "false").lower() != "true",
    reason="Real AI tests disabled. Set ENABLE_REAL_AI_TESTS=true to run.",
)


@pytest.mark.asyncio
@pytest.mark.real_ai
async def test_real_draft_creation_basic(
    skip_if_no_real_ai, client, api_key_header
):
    """Real AI: 기본 Draft 생성

    검증:
    - 실제 LLM API 호출
    - 실제 토큰 사용량
    - 의미 있는 출력 생성
    """
    request_data = {
        "user_id": 888,
        "topic_id": 999,
        "prompt": (
            "Write a brief introduction about quantum computing "
            "fundamentals"
        ),
        "selected_contents": [
            {
                "content_id": 1,
                "title": "Quantum Basics",
                "summary": "Foundation of quantum computing and qubits",
            }
        ],
        "model_alias": "gpt-4o-mini",
        "stream": False,
        "verbose": False,
    }

    response = await client.post(
        "/api/v1/topics/draft",
        json=request_data,
        headers=api_key_header,
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # 실제 LLM 출력 검증
    assert len(data["title"]) > 5
    assert len(data["draft_md"]) > 200  # 실제 출력은 충분히 김
    assert "quantum" in data["draft_md"].lower()

    # 실제 토큰 사용량
    usage = data["usage"]
    assert usage["total_input_tokens"] > 0
    assert usage["total_output_tokens"] > 0
    assert usage["total_wtu"] > 0

    # 로깅 (WTU 비용 확인용)
    print("\n✓ Real AI Usage:")
    print(f"  Input tokens: {usage['total_input_tokens']}")
    print(f"  Output tokens: {usage['total_output_tokens']}")
    print(f"  Total WTU: {usage['total_wtu']}")
    print(f"  Title: {data['title']}")
    print(f"  Draft length: {len(data['draft_md'])} chars")


@pytest.mark.asyncio
@pytest.mark.real_ai
async def test_real_draft_with_multiple_contents(
    skip_if_no_real_ai, client, api_key_header
):
    """Real AI: 다수 콘텐츠로 Draft 생성

    검증:
    - 여러 콘텐츠 통합 처리
    - Summarizer + Writer 협업
    """
    request_data = {
        "user_id": 888,
        "topic_id": 999,
        "prompt": (
            "Create a comprehensive guide about Python async programming"
        ),
        "selected_contents": [
            {
                "content_id": 1,
                "title": "Asyncio Basics",
                "summary": "Introduction to asyncio library and event loops",
            },
            {
                "content_id": 2,
                "title": "Async/Await Pattern",
                "summary": "Using async/await syntax for coroutines",
            },
            {
                "content_id": 3,
                "title": "Concurrency Patterns",
                "summary": (
                    "Common patterns for concurrent programming in Python"
                ),
            },
        ],
        "model_alias": "gpt-4o-mini",
        "stream": False,
    }

    response = await client.post(
        "/api/v1/topics/draft",
        json=request_data,
        headers=api_key_header,
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # 의미 있는 출력
    assert len(data["title"]) > 10
    assert len(data["draft_md"]) > 500
    assert any(
        keyword in data["draft_md"].lower()
        for keyword in ["async", "await", "asyncio", "python"]
    )

    # 에이전트별 사용량
    usage = data["usage"]
    assert "summarizer" in usage["agents"]
    assert "writer" in usage["agents"]

    print("\n✓ Multiple contents Real AI Usage:")
    print(f"  Total WTU: {usage['total_wtu']}")
    print(f"  Summarizer: {usage['agents']['summarizer']['wtu']} WTU")
    print(f"  Writer: {usage['agents']['writer']['wtu']} WTU")


@pytest.mark.asyncio
@pytest.mark.real_ai
async def test_real_streaming_flow(skip_if_no_real_ai, client, api_key_header):
    """Real AI: 스트리밍 모드

    검증:
    - SSE 이벤트 실시간 전송
    - 실제 LLM 출력 스트리밍
    """
    request_data = {
        "user_id": 888,
        "topic_id": 999,
        "prompt": "Write about REST API best practices",
        "selected_contents": [
            {
                "content_id": 1,
                "title": "REST Principles",
                "summary": "RESTful architecture fundamentals",
            }
        ],
        "model_alias": "gpt-4o-mini",
        "stream": True,
        "verbose": True,
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

    # SSE 이벤트 존재
    response_text = response.text
    assert "event: plan" in response_text
    assert "event: agent_start" in response_text
    assert "event: agent_done" in response_text
    assert "event: done" in response_text

    print("\\n✓ Real AI Streaming completed")


@pytest.mark.asyncio
@pytest.mark.real_ai
async def test_real_draft_empty_contents(
    skip_if_no_real_ai, client, api_key_header
):
    """Real AI: 콘텐츠 없이 Draft 생성

    검증:
    - 프롬프트만으로 초안 작성
    - Writer 단독 동작
    """
    request_data = {
        "user_id": 888,
        "topic_id": 999,
        "prompt": (
            "Write a short essay about the importance of software testing"
        ),
        "selected_contents": [],
        "model_alias": "gpt-4o-mini",
        "stream": False,
    }

    response = await client.post(
        "/api/v1/topics/draft",
        json=request_data,
        headers=api_key_header,
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # 콘텐츠 없어도 의미 있는 출력
    assert len(data["title"]) > 5
    assert len(data["draft_md"]) > 200
    draft_lower = data["draft_md"].lower()
    assert "test" in draft_lower or "software" in draft_lower

    wtu = data["usage"]["total_wtu"]
    print(f"\\n✓ Empty contents Real AI Usage: {wtu} WTU")


@pytest.mark.asyncio
@pytest.mark.real_ai
async def test_real_draft_output_quality(
    skip_if_no_real_ai, client, api_key_header
):
    """Real AI: 출력 품질 검증

    검증:
    - 마크다운 형식
    - Title 추출 정확성
    - 구조화된 문서
    """
    request_data = {
        "user_id": 888,
        "topic_id": 999,
        "prompt": (
            "Create a structured document about database indexing "
            "strategies"
        ),
        "selected_contents": [
            {
                "content_id": 1,
                "title": "Database Indexes",
                "summary": "Understanding B-tree and hash indexes",
            }
        ],
        "model_alias": "gpt-4o-mini",
        "stream": False,
    }

    response = await client.post(
        "/api/v1/topics/draft",
        json=request_data,
        headers=api_key_header,
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # Title 추출 확인
    assert data["title"]
    assert len(data["title"]) > 3
    assert len(data["title"]) < 200  # 제목은 적당한 길이

    # 마크다운 구조 확인
    draft = data["draft_md"]
    assert len(draft) > 100

    # 일반적인 마크다운 요소 존재 (실제 LLM이 생성)
    # 헤더, 리스트, 단락 등 (완벽하게 강제할 수 없으므로 느슨한 검증)
    assert any(char in draft for char in ["#", "-", "*", "\n\n"])

    print("\\n✓ Output quality check passed")
    print(f"  Title: {data['title']}")
    print("  Draft contains markdown elements: Yes")
