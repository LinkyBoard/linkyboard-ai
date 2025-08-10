import pytest

from app.user.v1.service import UserService
from app.user.v1.schemas import UserSyncRequest


@pytest.mark.asyncio
async def test_sync_and_get_user(db_session):
    service = UserService()
    request = UserSyncRequest(user_id=1, is_active=True)
    response = await service.sync_user(db_session, request)
    assert response.success is True
    assert response.user_id == 1
    assert response.created is True

    user_response = await service.get_user(db_session, 1)
    assert user_response is not None
    assert user_response.id == 1
