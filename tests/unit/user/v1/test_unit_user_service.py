
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from app.user.v1.service import UserService
from app.user.v1.schemas import UserSyncRequest, UserResponse
from app.core.models import User

@pytest.fixture
def user_service():
    with patch('app.user.v1.service.UserRepository') as MockUserRepository:
        mock_repo_instance = MockUserRepository.return_value
        mock_repo_instance.get_by_id = AsyncMock()
        mock_repo_instance.update = AsyncMock()
        mock_repo_instance.create = AsyncMock()
        service = UserService()
        service.user_repository = mock_repo_instance
        yield service

@pytest.fixture
def mock_session():
    return AsyncMock()

@pytest.mark.asyncio
async def test_sync_user_existing(user_service, mock_session):
    # Given
    user_id = 1
    request_data = UserSyncRequest(user_id=user_id, is_active=True)
    mock_existing_user = User(id=user_id, is_active=False)
    
    user_service.user_repository.get_by_id.return_value = mock_existing_user
    user_service.user_repository.update.return_value = User(id=user_id, is_active=True)

    # When
    response = await user_service.sync_user(mock_session, request_data)

    # Then
    user_service.user_repository.get_by_id.assert_called_once_with(mock_session, user_id)
    user_service.user_repository.update.assert_called_once()
    user_service.user_repository.create.assert_not_called()
    assert response.success is True
    assert response.user_id == user_id
    assert response.created is False

@pytest.mark.asyncio
async def test_sync_user_new(user_service, mock_session):
    # Given
    user_id = 2
    request_data = UserSyncRequest(user_id=user_id, is_active=True)
    
    user_service.user_repository.get_by_id.return_value = None
    user_service.user_repository.create.return_value = User(id=user_id, is_active=True)

    # When
    response = await user_service.sync_user(mock_session, request_data)

    # Then
    user_service.user_repository.get_by_id.assert_called_once_with(mock_session, user_id)
    user_service.user_repository.create.assert_called_once()
    user_service.user_repository.update.assert_not_called()
    assert response.success is True
    assert response.user_id == user_id
    assert response.created is True

@pytest.mark.asyncio
async def test_get_user_found(user_service, mock_session):
    # Given
    user_id = 1
    now = datetime.now()
    mock_user = User(
        id=user_id, 
        is_active=True, 
        ai_preferences="{}", 
        embedding_model_version="v1",
        created_at=now,
        updated_at=now
    )
    user_service.user_repository.get_by_id.return_value = mock_user

    # When
    response = await user_service.get_user(mock_session, user_id)

    # Then
    user_service.user_repository.get_by_id.assert_called_once_with(mock_session, user_id)
    assert isinstance(response, UserResponse)
    assert response.id == user_id

@pytest.mark.asyncio
async def test_get_user_not_found(user_service, mock_session):
    # Given
    user_id = 999
    user_service.user_repository.get_by_id.return_value = None

    # When
    response = await user_service.get_user(mock_session, user_id)

    # Then
    user_service.user_repository.get_by_id.assert_called_once_with(mock_session, user_id)
    assert response is None
