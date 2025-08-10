import asyncio
import pytest
from fastapi import BackgroundTasks

from app.collect.v1.clipper.service import ClipperService
from app.collect.v1.clipper.schemas import WebpageSyncRequest


@pytest.mark.asyncio
async def test_embedding_background_task(db_session, monkeypatch):
    service = ClipperService()
    background_tasks = BackgroundTasks()
    called = {"flag": False}

    async def fake_create_embeddings(session, item_id, content, **kwargs):
        called["flag"] = True
        return []

    monkeypatch.setattr(service.embedding_service, "create_embeddings", fake_create_embeddings)

    class DummySessionManager:
        async def __aenter__(self):
            return db_session
        async def __aexit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr("app.collect.v1.clipper.service.AsyncSessionLocal", lambda: DummySessionManager())

    request = WebpageSyncRequest(
        item_id=1,
        user_id=1,
        thumbnail="thumb",
        title="Test",
        url="http://example.com",
        summary=None,
        keywords=None,
        category="cat",
        memo=None,
        html_content="<html></html>",
    )
    await service.sync_webpage(db_session, background_tasks, request)

    assert len(background_tasks.tasks) == 1
    task = background_tasks.tasks[0]
    if asyncio.iscoroutinefunction(task.func):
        await task.func(*task.args, **task.kwargs)
    else:
        task.func(*task.args, **task.kwargs)

    assert called["flag"] is True
