import pytest

from app.core.repository import item_repository
from app.user.user_repository import user_repository


@pytest.mark.asyncio
async def test_create_and_get_item(db_session):
    await user_repository.get_or_create(db_session, user_id=1)
    item = await item_repository.create(
        db_session,
        id=1,
        user_id=1,
        item_type="webpage",
        title="Test Item",
        source_url="http://example.com",
    )
    fetched = await item_repository.get_by_id(db_session, 1)
    assert fetched.id == item.id
    assert fetched.title == "Test Item"


@pytest.mark.asyncio
async def test_search_by_title_or_description(db_session):
    await user_repository.get_or_create(db_session, user_id=1)
    await item_repository.create(
        db_session,
        id=1,
        user_id=1,
        item_type="webpage",
        title="Hello World",
        source_url="http://a.com",
    )
    await item_repository.create(
        db_session,
        id=2,
        user_id=1,
        item_type="webpage",
        title="Other",
        description="Interesting world",
        source_url="http://b.com",
    )
    results = await item_repository.search_by_title_or_description(db_session, 1, "Hello")
    assert len(results) == 1 and results[0].id == 1
    results2 = await item_repository.search_by_title_or_description(db_session, 1, "world")
    assert len(results2) == 2


@pytest.mark.asyncio
async def test_get_by_user_id(db_session):
    await user_repository.get_or_create(db_session, user_id=2)
    await item_repository.create(
        db_session,
        id=3,
        user_id=2,
        item_type="webpage",
        title="First",
        source_url="http://1.com",
    )
    await item_repository.create(
        db_session,
        id=4,
        user_id=2,
        item_type="webpage",
        title="Second",
        source_url="http://2.com",
    )
    items = await item_repository.get_by_user_id(db_session, user_id=2)
    assert {item.id for item in items} == {3, 4}
