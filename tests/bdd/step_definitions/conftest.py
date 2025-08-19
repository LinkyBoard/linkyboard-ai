"""
BDD 테스트를 위한 pytest 설정 및 공통 픽스처
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from uuid import uuid4

from app.main import app
from app.core.database import get_db
from app.core.models import Base, User, Item, ModelCatalog
from app.ai.providers.interface import AIResponse, TokenUsage


@pytest.fixture(scope="session")
def event_loop():
    """이벤트 루프 설정"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def bdd_db_session():
    """BDD 테스트용 인메모리 데이터베이스 세션"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture(scope="function")
async def bdd_async_client(bdd_db_session, mocker):
    """BDD 테스트용 FastAPI 클라이언트"""
    # Background task mocking
    mocker.patch("fastapi.BackgroundTasks.add_task", return_value=None)
    mocker.patch(
        "app.collect.v1.clipper.service.ClipperService._process_embedding_with_monitoring",
        return_value=None
    )
    
    async def _override_get_db():
        yield bdd_db_session

    app.dependency_overrides[get_db] = _override_get_db
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
def bdd_board_id():
    """BDD 테스트용 보드 ID"""
    return uuid4()


@pytest.fixture
def bdd_user_id():
    """BDD 테스트용 사용자 ID"""
    return 1001


@pytest.fixture
def bdd_test_user(bdd_user_id):
    """BDD 테스트용 사용자 객체"""
    return User(id=bdd_user_id, email=f"test{bdd_user_id}@example.com")


@pytest.fixture
def bdd_test_item(bdd_user_id):
    """BDD 테스트용 아이템 객체"""
    return Item(
        id=123,
        user_id=bdd_user_id,
        title="테스트 아이템",
        source_url="https://example.com",
        item_type="webpage",
        summary="테스트 요약",
        raw_content="테스트 내용",
        category="기술"
    )


@pytest.fixture
def bdd_gpt_model():
    """BDD 테스트용 GPT 모델"""
    return ModelCatalog(
        id=1,
        alias="gpt-3.5-turbo",
        model_name="gpt-3.5-turbo",
        provider="openai",
        model_type="llm",
        role_mask=0b111,
        price_per_input_token=0.0015,
        price_per_output_token=0.002,
        price_currency="USD",
        input_token_weight=1.0,
        output_token_weight=4.0,
        status="active",
        version="0613",
        description="OpenAI GPT-3.5 Turbo model"
    )


@pytest.fixture
def bdd_mock_ai_response():
    """BDD 테스트용 AI 응답 모킹"""
    return AIResponse(
        content="테스트 AI 응답입니다.",
        token_usage=TokenUsage(
            input_tokens=50,
            output_tokens=100,
            total_tokens=150
        ),
        model="gpt-3.5-turbo",
        provider="openai"
    )


@pytest.fixture
def bdd_mock_ai_router(mocker, bdd_mock_ai_response):
    """BDD 테스트용 AI 라우터 모킹"""
    with patch('app.ai.providers.router.AIRouter') as mock_router:
        mock_instance = AsyncMock()
        mock_instance.generate_chat_completion.return_value = bdd_mock_ai_response
        mock_instance.generate_webpage_tags.return_value = ["tag1", "tag2", "tag3"]
        mock_instance.recommend_webpage_category.return_value = "기술"
        mock_router.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def bdd_mock_openai_service(mocker):
    """BDD 테스트용 OpenAI 서비스 모킹"""
    with patch('app.ai.openai_service.openai_service') as mock:
        mock.generate_chat_completion = AsyncMock(return_value={
            "content": "Mock OpenAI response",
            "input_tokens": 50,
            "output_tokens": 100
        })
        yield mock


@pytest.fixture
def bdd_mock_model_catalog_service(mocker, bdd_gpt_model):
    """BDD 테스트용 모델 카탈로그 서비스 모킹"""
    with patch('app.core.model_catalog_service.model_catalog_service') as mock:
        mock.get_model_by_alias = AsyncMock(return_value=bdd_gpt_model)
        mock.get_active_models = AsyncMock(return_value=[bdd_gpt_model])
        yield mock


@pytest.fixture
def bdd_html_content():
    """BDD 테스트용 HTML 컨텐츠"""
    return "<html><body><h1>테스트 페이지</h1><p>테스트 내용입니다.</p></body></html>"


@pytest.fixture
def bdd_large_html_content():
    """BDD 테스트용 대용량 HTML 컨텐츠"""
    return "<html><body>" + "x" * 10000 + "</body></html>"