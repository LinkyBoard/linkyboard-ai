"""
Functional tests for User API router endpoints.
Fixed version to avoid event loop and database connection issues.
"""

import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import delete
from unittest.mock import Mock, patch

from app.main import app
from app.core.database import get_db
from app.core.config import settings
from app.core import models


# Use session-scoped event loop policy
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# Add process isolation marker to avoid parallel execution issues
pytestmark = pytest.mark.asyncio


# --- Test Database Setup ---
# Use completely isolated test engine per test
def get_test_engine():
    """Create a fresh test engine for each test to avoid connection conflicts."""
    return create_async_engine(
        settings.database_url, 
        echo=False, 
        pool_pre_ping=True,
        pool_recycle=30,      # Very short recycle time 
        pool_size=1,          # Single connection per test
        max_overflow=0,       # No overflow connections
        pool_timeout=5,       # Short timeout
    )

# Remove module-level engine to avoid sharing between tests
# Each test will create its own engine


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a completely isolated session with its own engine for each test.
    """
    # Create a fresh engine for this test only
    engine = get_test_engine()
    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # Create a fresh session 
    session = SessionLocal()
    try:
        yield session
    finally:
        try:
            # Clean up test data after each test
            await session.execute(delete(models.User).where(models.User.id >= 6000))
            await session.commit()
        except Exception:
            try:
                await session.rollback()
            except Exception:
                pass  # Ignore rollback errors during cleanup
        finally:
            try:
                await session.close()
            except Exception:
                pass  # Ignore close errors during cleanup
            finally:
                # Dispose the engine after the test
                try:
                    await engine.dispose()
                except Exception:
                    pass  # Ignore disposal errors


@pytest.fixture(scope="function") 
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provides a test client with completely isolated dependency management."""
    
    # Simple dependency override with fresh session
    async def _override_get_db():
        yield db_session

    # Clear any existing overrides first and wait a bit
    app.dependency_overrides.clear()
    await asyncio.sleep(0.01)
    app.dependency_overrides[get_db] = _override_get_db
    
    # Mock only essential background tasks to prevent event loop conflicts
    with patch("fastapi.BackgroundTasks.add_task", return_value=None):
        try:
            # Use a shorter timeout to avoid hanging
            async with AsyncClient(
                transport=ASGITransport(app=app), 
                base_url="http://test",
                timeout=5.0  # Shorter timeout
            ) as client:
                yield client
        finally:
            # Clean up dependency overrides
            app.dependency_overrides.clear()
            # Small delay to let connections settle before next test
            await asyncio.sleep(0.05)


@pytest.fixture(scope="session", autouse=True)
async def cleanup_on_session_end():
    """Clean up any remaining resources at the end of test session."""
    yield
    # No global engine to clean up since each test creates its own


# --- Test Cases ---

@pytest.mark.asyncio
async def test_sync_user_creates_new_user(async_client: AsyncClient, db_session: AsyncSession):
    """
    Tests creating a new user via the /sync endpoint.
    """
    # Given: A new user
    test_user_id = 6001
    request_data = {
        "user_id": test_user_id,
        "is_active": True
    }
    
    # When: Make the API request
    response = await async_client.post("/api/v1/user/sync", json=request_data)
    
    # Then: Verify sync response (UserSyncResponse)
    assert response.status_code == 200
    response_data = response.json()
    
    # Check sync response structure
    assert response_data["success"] == True
    assert response_data["user_id"] == test_user_id
    assert response_data["created"] == True
    assert "message" in response_data


@pytest.mark.asyncio
async def test_sync_user_validation_errors(async_client: AsyncClient):
    """
    Tests validation errors for the /sync endpoint.
    """
    # Test missing user_id
    response = await async_client.post("/api/v1/user/sync", json={})
    assert response.status_code == 422
    
    # Test invalid user_id type
    response = await async_client.post("/api/v1/user/sync", json={"user_id": "invalid"})
    assert response.status_code == 422


@pytest.mark.asyncio  
async def test_get_user_validation_errors(async_client: AsyncClient):
    """
    Tests validation errors for the /{user_id} endpoint.
    """
    # Test invalid user_id format
    response = await async_client.get("/api/v1/user/invalid")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_user_existing_user(async_client: AsyncClient, db_session: AsyncSession):
    """
    Tests retrieving an existing user via the /{user_id} endpoint.
    Using API-based approach to avoid direct DB manipulation issues.
    """
    # Given: Create a user via API first (this is known to work)
    test_user_id = 6003
    create_request_data = {
        "user_id": test_user_id,
        "is_active": True
    }
    
    # Create user via API
    create_response = await async_client.post("/api/v1/user/sync", json=create_request_data)
    assert create_response.status_code == 200
    create_data = create_response.json()
    assert create_data["success"] is True
    assert create_data["created"] is True
    
    # Small delay to ensure consistency
    await asyncio.sleep(0.1)
    
    # When: Get the user via API
    response = await async_client.get(f"/api/v1/user/{test_user_id}")
    
    # Then: Should return the user
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_user_id
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_get_user_not_found(async_client: AsyncClient):
    """
    Tests retrieving a non-existent user via the /{user_id} endpoint.
    """
    # Given: A user ID that doesn't exist
    test_user_id = 99999
    
    # When: Try to get the user
    response = await async_client.get(f"/api/v1/user/{test_user_id}")
    
    # Then: Should return 404
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_sync_user_with_default_is_active(async_client: AsyncClient, db_session: AsyncSession):
    """
    Tests user sync with default is_active value (should be True).
    """
    # Given: A new user without explicit is_active value
    test_user_id = 6004
    request_data = {
        "user_id": test_user_id
        # is_active not specified, should default to True
    }

    # When: Make the API request
    response = await async_client.post("/api/v1/user/sync", json=request_data)

    # Then: Verify sync response
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["user_id"] == test_user_id
    assert data["created"] is True
@pytest.mark.asyncio
async def test_sync_user_updates_existing_user(async_client: AsyncClient, db_session: AsyncSession):
    """
    Tests updating an existing user via the /sync endpoint.
    Using API-based approach for better stability.
    """
    # Given: Create an existing user via API first
    test_user_id = 6002
    
    # Create user with initial state (is_active=False)
    create_request_data = {
        "user_id": test_user_id,
        "is_active": False
    }
    create_response = await async_client.post("/api/v1/user/sync", json=create_request_data)
    assert create_response.status_code == 200
    create_data = create_response.json()
    assert create_data["success"] is True
    assert create_data["created"] is True
    
    # Small delay for consistency
    await asyncio.sleep(0.1)
    
    # When: Update the user via sync API
    update_request_data = {
        "user_id": test_user_id,
        "is_active": True  # Update to True
    }
    response = await async_client.post("/api/v1/user/sync", json=update_request_data)
    
    # Then: Should successfully update
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["user_id"] == test_user_id
    assert data["created"] is False  # Should be False since user existed
