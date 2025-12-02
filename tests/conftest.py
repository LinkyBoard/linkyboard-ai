"""테스트 설정"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


@pytest_asyncio.fixture
async def client():
    """비동기 테스트 클라이언트"""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
def anyio_backend():
    """anyio 백엔드 설정"""
    return "asyncio"


@pytest.fixture
def api_key_header():
    """Internal API Key 헤더"""
    return {"X-Internal-Api-Key": settings.internal_api_key}
