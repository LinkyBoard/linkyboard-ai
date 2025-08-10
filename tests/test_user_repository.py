import pytest

from app.user.user_repository import user_repository


@pytest.mark.asyncio
async def test_get_or_create(db_session):
    user = await user_repository.get_or_create(db_session, user_id=1)
    assert user.id == 1
    assert user.is_active is True


@pytest.mark.asyncio
async def test_activate_and_deactivate_user(db_session):
    await user_repository.get_or_create(db_session, user_id=2)
    await user_repository.deactivate_user(db_session, 2)
    user = await user_repository.get_by_id(db_session, 2)
    assert user.is_active is False

    await user_repository.activate_user(db_session, 2)
    user = await user_repository.get_by_id(db_session, 2)
    assert user.is_active is True
