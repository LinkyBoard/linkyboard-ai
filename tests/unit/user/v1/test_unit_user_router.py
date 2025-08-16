
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from unittest.mock import AsyncMock, patch
from datetime import datetime

from app.user.v1.router import router as user_router
from app.user.v1.schemas import UserSyncResponse, UserResponse

# Create a test app to include the router
app = FastAPI()
app.include_router(user_router)

@pytest.fixture
def mock_user_service():
    with patch('app.user.v1.router.user_service', new_callable=AsyncMock) as mock_service:
        yield mock_service

@pytest.mark.asyncio
async def test_sync_user_success(mock_user_service):
    # Given
    user_id = 1
    request_data = {"user_id": user_id, "is_active": True}
    mock_user_service.sync_user.return_value = UserSyncResponse(
        success=True,
        message="사용자가 성공적으로 동기화되었습니다.",
        user_id=user_id,
        created=False
    )

    # When
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/user/sync", json=request_data)

    # Then
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["user_id"] == user_id

@pytest.mark.asyncio
async def test_sync_user_error(mock_user_service):
    # Given
    user_id = 1
    request_data = {"user_id": user_id, "is_active": True}
    mock_user_service.sync_user.side_effect = Exception("DB error")

    # When
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/user/sync", json=request_data)

    # Then
    assert response.status_code == 500
    assert response.json() == {"detail": "DB error"}

@pytest.mark.asyncio
async def test_get_user_found(mock_user_service):
    # Given
    user_id = 1
    now = datetime.now()
    mock_user_service.get_user.return_value = UserResponse(
        id=user_id,
        is_active=True,
        last_sync_at=now,
        ai_preferences="{}",
        embedding_model_version="v1",
        created_at=now,
        updated_at=now
    )

    # When
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/api/v1/user/{user_id}")

    # Then
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == user_id

@pytest.mark.asyncio
async def test_get_user_not_found(mock_user_service):
    # Given
    user_id = 999
    mock_user_service.get_user.return_value = None

    # When
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/api/v1/user/{user_id}")

    # Then
    assert response.status_code == 404
    assert response.json() == {"detail": "사용자를 찾을 수 없습니다."}

@pytest.mark.asyncio
async def test_get_user_error(mock_user_service):
    # Given
    user_id = 1
    mock_user_service.get_user.side_effect = Exception("Internal error")

    # When
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/api/v1/user/{user_id}")

    # Then
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal error"}
