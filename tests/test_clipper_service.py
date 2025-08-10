import pytest
from fastapi import BackgroundTasks

from app.collect.v1.clipper.service import ClipperService
from app.collect.v1.clipper.schemas import WebpageSyncRequest
from app.user.user_repository import user_repository


@pytest.mark.asyncio
async def test_sync_webpage_creates_item_and_user(db_session):
    service = ClipperService()
    background_tasks = BackgroundTasks()
    request = WebpageSyncRequest(
        item_id=1,
        user_id=1,
        thumbnail="thumb",
        title="Test Page",
        url="http://example.com",
        summary=None,
        keywords=None,
        category="test",
        memo=None,
        html_content="<html></html>",
    )
    response = await service.sync_webpage(db_session, background_tasks, request)
    assert response.success is True

    item = await service.item_repository.get_by_id(db_session, 1)
    assert item is not None and item.title == "Test Page"

    user = await user_repository.get_by_id(db_session, 1)
    assert user is not None

    assert len(background_tasks.tasks) == 1
