"""Topics 도메인 라우터

Topics Agent 오케스트레이션 관련 API 엔드포인트입니다.
"""

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import verify_internal_api_key
from app.core.schemas import APIResponse, create_response
from app.domains.topics.agents import (
    ResearcherAgent,
    SummarizerAgent,
    WriterAgent,
)
from app.domains.topics.orchestration import (
    DraftOrchestrationInput,
    ExecutionResult,
    OrchestrationExecutor,
    StreamEvent,
    TopicsOrchestrator,
    UsageSummary,
)
from app.domains.topics.schemas import (
    TopicsAskRequest,
    TopicsAskResponse,
    TopicsDraftRequest,
    TopicsDraftResponse,
    TopicsUsage,
)

router = APIRouter()


def get_topics_orchestrator(
    session: AsyncSession = Depends(get_db),
) -> TopicsOrchestrator:
    """요청마다 새로운 오케스트레이터 인스턴스를 생성"""
    executor = OrchestrationExecutor(session=session)
    executor.register_agent(SummarizerAgent())
    executor.register_agent(ResearcherAgent())
    executor.register_agent(WriterAgent())
    return TopicsOrchestrator(executor)


@router.post(
    "/ask",
    response_model=APIResponse[TopicsAskResponse],
    dependencies=[Depends(verify_internal_api_key)],
)
async def ask_topics(
    request: TopicsAskRequest,
):
    """ask API 스켈레톤
    동적 오케스트레이션 기능
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="ask 오케스트레이션은 아직 구현되지 않았습니다.",
    )


@router.post(
    "/draft",
    response_model=APIResponse[TopicsDraftResponse],
    dependencies=[Depends(verify_internal_api_key)],
)
async def create_draft(
    request: TopicsDraftRequest,
    orchestrator: TopicsOrchestrator = Depends(get_topics_orchestrator),
):
    """draft API"""
    draft_input = DraftOrchestrationInput(
        user_id=request.user_id,
        topic_id=request.topic_id,
        prompt=request.prompt,
        selected_contents=[
            content.model_dump() for content in request.selected_contents
        ],
        stream=request.stream,
        verbose=request.verbose,
        metadata={},
    )

    if request.stream:
        return await _create_streaming_response(orchestrator, draft_input)

    result = await orchestrator.run_draft(draft_input)
    response = _build_draft_response(result)

    return create_response(
        data=response,
        message="초안 생성 작업이 완료되었습니다.",
    )


async def _create_streaming_response(
    orchestrator: TopicsOrchestrator,
    draft_input: DraftOrchestrationInput,
) -> StreamingResponse:
    """Executor 이벤트를 SSE로 중계"""
    queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue()

    async def event_callback(event: StreamEvent) -> None:
        await queue.put(event)

    async def runner() -> None:
        try:
            result = await orchestrator.run_draft(
                draft_input,
                event_callback=event_callback,
            )
            await queue.put(
                StreamEvent(event="done", data=_build_done_payload(result))
            )
        except Exception as exc:  # noqa: BLE001
            await queue.put(
                StreamEvent(
                    event="error",
                    data={
                        "message": "오케스트레이션 실행 중 오류가 발생했습니다.",
                        "detail": str(exc),
                    },
                )
            )
        finally:
            await queue.put(None)

    asyncio.create_task(runner())

    async def event_generator() -> AsyncGenerator[bytes, None]:
        while True:
            event = await queue.get()
            if event is None:
                break
            yield _format_sse(event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


def _build_draft_response(result: ExecutionResult) -> TopicsDraftResponse:
    payload = result.final_output or {}
    return TopicsDraftResponse(
        title=payload.get("title"),
        draft_md=payload.get("draft_md"),
        warnings=result.warnings,
        usage=_map_usage_summary(result.usage),
    )


def _build_done_payload(result: ExecutionResult) -> dict:
    response = _build_draft_response(result)
    return {
        "data": response.model_dump(),
        "success": True,
    }


def _map_usage_summary(usage: UsageSummary | None) -> TopicsUsage | None:
    if usage is None:
        return None

    return TopicsUsage(
        total_input_tokens=usage.total_input_tokens,
        total_output_tokens=usage.total_output_tokens,
        total_wtu=usage.total_wtu,
    )


def _format_sse(event: StreamEvent) -> bytes:
    payload = json.dumps(event.data, ensure_ascii=False)
    return f"event: {event.event}\ndata: {payload}\n\n".encode("utf-8")
