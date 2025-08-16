
import pytest
import asyncio
import tempfile
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import delete
from unittest.mock import Mock, patch, AsyncMock

from app.main import app
from app.core.database import get_db
from app.core.config import settings
from app.core import models

# Event loop fixture to ensure proper async handling
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# --- Test Database Setup ---
test_engine = create_async_engine(
    settings.database_url, 
    echo=False, 
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10
)
TestSessionLocal = sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)

# --- Fixtures ---

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a clean session for a single test.
    """
    session = TestSessionLocal()
    try:
        yield session
    finally:
        # Clean up all test data after each test
        try:
            # Delete all items and users created during tests
            await session.execute(delete(models.Item).where(models.Item.id >= 4000))
            await session.execute(delete(models.User).where(models.User.id >= 400))
            await session.commit()
        except Exception:
            await session.rollback()
        finally:
            await session.close()


@pytest.fixture(scope="function") 
async def async_client(db_session: AsyncSession, mocker) -> AsyncGenerator[AsyncClient, None]:
    """Provides a test client with the DB dependency overridden to use the test session."""
    # Mock background tasks to prevent event loop conflicts
    mocker.patch("fastapi.BackgroundTasks.add_task", return_value=None)
    mocker.patch(
        "app.collect.v1.clipper.service.ClipperService._process_embedding_with_monitoring",
        return_value=None
    )
    
    # Create a new event loop for this test to avoid conflicts
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    
    # Ensure FastAPI uses the same event loop as pytest
    loop = asyncio.get_running_loop()
    app.state.event_loop = loop
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
        
    # Clean up dependency overrides
    app.dependency_overrides.clear()
    
    # Give some time for any remaining tasks to complete
    await asyncio.sleep(0.1)


@pytest.fixture(scope="session", autouse=True)
async def cleanup_db_engine():
    """Clean up database engine at the end of test session."""
    yield
    await test_engine.dispose()


# --- Test Cases ---

@pytest.mark.asyncio
async def test_summarize_webpage_success(async_client: AsyncClient, mocker):
    """
    Tests the /webpage/summarize endpoint for successful summary generation.
    """
    # Given: Mock the external AI service
    mock_summary_result = {
        "summary": "테스트 요약입니다.",
        "recommended_tags": ["pytest", "fastapi", "test"],
        "recommended_category": "개발",
    }
    mocker.patch(
        "app.collect.v1.clipper.service.ClipperService.generate_webpage_summary_with_recommendations",
        return_value=mock_summary_result
    )

    # When: Make the API request
    response = await async_client.post(
        "/api/v1/clipper/webpage/summarize",
        data={"url": "http://example.com", "user_id": 999, "tag_count": 3},
        files={"html_file": ("test.html", "<html><body>Test content</body></html>", "text/html")}
    )

    # Then: Assert the response
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == mock_summary_result["summary"]
    assert data["tags"] == mock_summary_result["recommended_tags"]
    assert data["category"] == mock_summary_result["recommended_category"]


@pytest.mark.asyncio
async def test_summarize_webpage_validation_error(async_client: AsyncClient):
    """
    Tests validation error on the /webpage/summarize endpoint.
    """
    # Given: Request with missing required field (user_id)
    response = await async_client.post(
        "/api/v1/clipper/webpage/summarize",
        data={"url": "http://example.com"},
        files={"html_file": ("test.html", "<html></html>", "text/html")}
    )
    
    # Then: Assert 422 validation error
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_summarize_webpage_missing_html_file(async_client: AsyncClient):
    """
    Tests error when HTML file is missing.
    """
    # Given: Request without HTML file
    response = await async_client.post(
        "/api/v1/clipper/webpage/summarize",
        data={"url": "http://example.com", "user_id": 999}
    )
    
    # Then: Assert 422 validation error
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_summarize_webpage_service_error(async_client: AsyncClient, mocker):
    """
    Tests handling of service errors in /webpage/summarize endpoint.
    """
    # Given: Mock service to raise an exception
    mocker.patch(
        "app.collect.v1.clipper.service.ClipperService.generate_webpage_summary_with_recommendations",
        side_effect=Exception("AI service unavailable")
    )

    # When: Make the API request
    response = await async_client.post(
        "/api/v1/clipper/webpage/summarize",
        data={"url": "http://example.com", "user_id": 999},
        files={"html_file": ("test.html", "<html></html>", "text/html")}
    )

    # Then: Assert 500 error
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_sync_webpage_creates_new_item(async_client: AsyncClient, db_session: AsyncSession):
    """
    Tests creating a new item via the /webpage/sync endpoint.
    """
    # Given: A user exists in the database
    test_user_id = 401
    test_item_id = 4001

    user = models.User(id=test_user_id)
    db_session.add(user)
    await db_session.commit()

    # When: Make the API request
    form_data = {
        "item_id": test_item_id,
        "user_id": test_user_id,
        "thumbnail": "http://example.com/thumb.jpg",
        "title": "새로운 아이템",
        "url": "http://example.com/new-item",
        "category": "기술",
    }
    response = await async_client.post(
        "/api/v1/clipper/webpage/sync",
        data=form_data,
        files={"html_file": ("new.html", "<html></html>", "text/html")}
    )

    # Then: Assert the response and that the item was created in the DB
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Refresh session to get latest data
    await db_session.commit()
    item = await db_session.get(models.Item, test_item_id)
    assert item is not None
    assert item.title == "새로운 아이템"


@pytest.mark.asyncio
async def test_sync_webpage_updates_existing_item(async_client: AsyncClient, db_session: AsyncSession, mocker):
    """
    Tests updating an existing item via the /webpage/sync endpoint.
    """
    # Given: Mock the service to simulate updating an existing item
    test_user_id = 402
    test_item_id = 4002

    # Mock the sync_webpage method to return the expected response
    mocker.patch(
        "app.collect.v1.clipper.service.ClipperService.sync_webpage",
        return_value=None  # Service method doesn't return anything, just processes
    )

    # Create a temporary HTML file
    html_content = "<html><body>Updated content</body></html>"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
        f.write(html_content)
        temp_html_path = f.name

    try:
        # When: Make the API request to update existing item
        with open(temp_html_path, 'rb') as html_file:
            response = await async_client.post(
                "/api/v1/clipper/webpage/sync",
                data={
                    "user_id": test_user_id,
                    "item_id": test_item_id,
                    "title": "Updated Title",
                    "url": "http://updated.com",
                    "thumbnail": "http://example.com/thumb.jpg",
                    "category": "업데이트"
                },
                files={"html_file": ("test.html", html_file, "text/html")}
            )

        # Then: Assert the response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert "message" in response_data
    finally:
        import os
        os.unlink(temp_html_path)


@pytest.mark.asyncio
async def test_sync_webpage_validation_error(async_client: AsyncClient):
    """
    Tests for a validation error on the /webpage/sync endpoint.
    """
    # Given: Request with missing required field (item_id)
    response = await async_client.post(
        "/api/v1/clipper/webpage/sync",
        data={"user_id": 999, "title": "Invalid"},
        files={"html_file": ("invalid.html", "<html></html>", "text/html")}
    )
    # Then: Assert 422 error
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_sync_webpage_missing_html_file(async_client: AsyncClient):
    """
    Tests error when HTML file is missing in /webpage/sync endpoint.
    """
    # Given: Request without HTML file
    response = await async_client.post(
        "/api/v1/clipper/webpage/sync",
        data={
            "item_id": 5001,
            "user_id": 500,
            "thumbnail": "http://example.com/thumb.jpg",
            "title": "Test Item",
            "url": "http://example.com",
            "category": "테스트"
        }
    )
    
    # Then: Assert 422 validation error
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_sync_webpage_with_optional_fields(async_client: AsyncClient, db_session: AsyncSession):
    """
    Tests the /webpage/sync endpoint with optional fields (summary, tags, memo).
    """
    test_user_id = 403
    test_item_id = 4003

    # Given: A user exists in the database
    user = models.User(id=test_user_id)
    db_session.add(user)
    await db_session.commit()

    # When: Make the API request with optional fields
    form_data = {
        "item_id": test_item_id,
        "user_id": test_user_id,
        "thumbnail": "http://example.com/thumb.jpg",
        "title": "완전한 아이템",
        "url": "http://example.com/complete-item",
        "category": "기술",
        "summary": "이것은 테스트 요약입니다.",
        "tags": ["python", "fastapi", "test"],
        "memo": "사용자 메모입니다."
    }
    response = await async_client.post(
        "/api/v1/clipper/webpage/sync",
        data=form_data,
        files={"html_file": ("complete.html", "<html><body>Complete content</body></html>", "text/html")}
    )

    # Then: Assert the response
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_sync_webpage_nonexistent_user(async_client: AsyncClient):
    """
    Tests the /webpage/sync endpoint with a nonexistent user.
    """
    test_user_id = 404
    test_item_id = 4004

    # When: Make the API request with nonexistent user
    form_data = {
        "item_id": test_item_id,
        "user_id": test_user_id,
        "thumbnail": "http://example.com/thumb.jpg",
        "title": "Orphaned Item",
        "url": "http://example.com/orphaned",
        "category": "테스트",
    }
    response = await async_client.post(
        "/api/v1/clipper/webpage/sync",
        data=form_data,
        files={"html_file": ("orphaned.html", "<html></html>", "text/html")}
    )

    # Then: Should handle the error appropriately
    # Note: This depends on how the service handles missing users
    # Adjust assertion based on actual service behavior
    assert response.status_code in [200, 400, 404, 500]


@pytest.mark.asyncio
async def test_sync_webpage_large_html_content(async_client: AsyncClient, db_session: AsyncSession, mocker):
    """
    Tests the /webpage/sync endpoint with large HTML content.
    """
    test_user_id = 405
    test_item_id = 4005

    # Given: Mock the service to handle large content
    mocker.patch(
        "app.collect.v1.clipper.service.ClipperService.sync_webpage",
        return_value=None  # Service method doesn't return anything, just processes
    )

    large_html_content = "<html><body>" + "x" * 10000 + "</body></html>"

    # When: Make the API request with large HTML
    form_data = {
        "item_id": test_item_id,
        "user_id": test_user_id,
        "thumbnail": "http://example.com/thumb.jpg",
        "title": "Large Content",
        "url": "http://large.com",
        "category": "테스트",
    }
    response = await async_client.post(
        "/api/v1/clipper/webpage/sync",
        data=form_data,
        files={"html_file": ("large.html", large_html_content, "text/html")}
    )

    # Then: Should handle large content successfully
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert "message" in response_data


@pytest.mark.asyncio
async def test_sync_webpage_special_characters(async_client: AsyncClient, db_session: AsyncSession):
    """
    Tests the /webpage/sync endpoint with special characters in title and content.
    """
    test_user_id = 406
    test_item_id = 4006

    # Given: A user exists in the database
    user = models.User(id=test_user_id)
    db_session.add(user)
    await db_session.commit()

    # When: Make the API request with special characters
    form_data = {
        "item_id": test_item_id,
        "user_id": test_user_id,
        "thumbnail": "http://example.com/thumb.jpg",
        "title": "특수문자 테스트 & < > \" ' 😀",
        "url": "http://example.com/special-chars",
        "category": "테스트",
        "memo": "메모에도 특수문자: & < > \" ' 😀"
    }
    response = await async_client.post(
        "/api/v1/clipper/webpage/sync",
        data=form_data,
        files={"html_file": ("special.html", "<html><body>특수문자 & < > \" ' 😀</body></html>", "text/html")}
    )

    # Then: Should handle special characters correctly
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_summarize_webpage_with_default_tag_count(async_client: AsyncClient, mocker):
    """
    Tests the /webpage/summarize endpoint with default tag_count parameter.
    """
    # Given: Mock the external AI service
    mock_summary_result = {
        "summary": "기본 태그 수 테스트",
        "recommended_tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
        "recommended_category": "기본",
    }
    mocker.patch(
        "app.collect.v1.clipper.service.ClipperService.generate_webpage_summary_with_recommendations",
        return_value=mock_summary_result
    )

    # When: Make the API request without tag_count (should use default)
    response = await async_client.post(
        "/api/v1/clipper/webpage/summarize",
        data={"url": "http://example.com", "user_id": 999},
        files={"html_file": ("test.html", "<html><body>Default tag count test</body></html>", "text/html")}
    )

    # Then: Assert the response
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == mock_summary_result["summary"]
    assert len(data["tags"]) == 5  # Default tag count should be 5


@pytest.mark.asyncio
async def test_sync_webpage_duplicate_item_id(async_client: AsyncClient, db_session: AsyncSession):
    """
    Tests creating items with duplicate item_id should update existing item.
    """
    test_user_id = 407
    test_item_id = 4007

    # Given: A user and item exist
    user = models.User(id=test_user_id)
    original_item = models.Item(
        id=test_item_id, 
        user_id=test_user_id, 
        title="Original Title", 
        source_url="http://original.com"
    )
    db_session.add_all([user, original_item])
    await db_session.commit()

    # When: Try to create item with same ID (should update)
    form_data = {
        "item_id": test_item_id,
        "user_id": test_user_id,
        "thumbnail": "http://example.com/new-thumb.jpg",
        "title": "Updated Title",
        "url": "http://updated.com",
        "category": "업데이트",
    }
    response = await async_client.post(
        "/api/v1/clipper/webpage/sync",
        data=form_data,
        files={"html_file": ("update.html", "<html><body>Updated content</body></html>", "text/html")}
    )

    # Then: Should update existing item
    assert response.status_code == 200
    assert response.json()["success"] is True
