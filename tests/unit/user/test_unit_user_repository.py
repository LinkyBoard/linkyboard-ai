
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.user.user_repository import UserRepository
from app.core.models import User

@pytest.fixture
def user_repository():
    return UserRepository()

@pytest.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    
    # Mock the execute method to return a mock result object
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute.return_value = mock_result
    
    return session

@pytest.mark.asyncio
async def test_get_or_create_existing_user(user_repository, mock_session):
    # Given
    user_id = 1
    mock_user = User(id=user_id, is_active=True)
    mock_session.execute.return_value.scalar_one_or_none.return_value = mock_user

    # When
    user = await user_repository.get_or_create(mock_session, user_id)

    # Then
    assert user == mock_user
    mock_session.add.assert_not_called()

@pytest.mark.asyncio
async def test_get_or_create_new_user(user_repository, mock_session):
    # Given
    user_id = 1
    mock_session.execute.return_value.scalar_one_or_none.return_value = None

    # When
    user = await user_repository.get_or_create(mock_session, user_id)

    # Then
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once_with(user)
    assert user.id == user_id
    assert user.is_active is True

@pytest.mark.asyncio
async def test_activate_user(user_repository, mock_session):
    # Given
    user_id = 1
    mock_user = User(id=user_id, is_active=False)
    user_repository.get_by_id = AsyncMock(return_value=mock_user)

    # When
    user = await user_repository.activate_user(mock_session, user_id)

    # Then
    assert user.is_active is True
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once_with(user)

@pytest.mark.asyncio
async def test_deactivate_user(user_repository, mock_session):
    # Given
    user_id = 1
    mock_user = User(id=user_id, is_active=True)
    user_repository.get_by_id = AsyncMock(return_value=mock_user)

    # When
    user = await user_repository.deactivate_user(mock_session, user_id)

    # Then
    assert user.is_active is False
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once_with(user)

@pytest.mark.asyncio
async def test_update_sync_time(user_repository, mock_session):
    # Given
    user_id = 1
    mock_user = User(id=user_id)
    user_repository.get_by_id = AsyncMock(return_value=mock_user)

    # When
    await user_repository.update_sync_time(mock_session, user_id)

    # Then
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once_with(mock_user)

@pytest.mark.asyncio
async def test_update_ai_preferences(user_repository, mock_session):
    # Given
    user_id = 1
    preferences = '{"some": "preference"}'
    mock_user = User(id=user_id)
    user_repository.get_by_id = AsyncMock(return_value=mock_user)

    # When
    user = await user_repository.update_ai_preferences(mock_session, user_id, preferences)

    # Then
    assert user.ai_preferences == preferences
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once_with(user)

@pytest.mark.asyncio
async def test_update_embedding_model_version(user_repository, mock_session):
    # Given
    user_id = 1
    version = "v2"
    mock_user = User(id=user_id, embedding_model_version="v1")
    user_repository.get_by_id = AsyncMock(return_value=mock_user)

    # When
    user = await user_repository.update_embedding_model_version(mock_session, user_id, version)

    # Then
    assert user.embedding_model_version == version
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once_with(user)
