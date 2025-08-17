"""
Model Picker v1 - pytest 설정 및 공통 픽스처
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from uuid import uuid4

from app.main import app
from app.core.database import get_db
from app.core.models import Base, ModelCatalog, BoardModelPolicy, UserModelPolicy


@pytest.fixture(scope="session")
def event_loop():
    """이벤트 루프 설정"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client():
    """테스트 클라이언트"""
    return TestClient(app)


@pytest.fixture
async def db_session():
    """테스트용 데이터베이스 세션"""
    # 인메모리 SQLite 사용
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture
def mock_db_dependency(db_session):
    """데이터베이스 의존성 Mock"""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def sample_board_id():
    """샘플 보드 ID"""
    return uuid4()


@pytest.fixture
def sample_user_id():
    """샘플 사용자 ID"""
    return 1001


@pytest.fixture
def sample_gpt4o_mini():
    """GPT-4o-mini 모델 샘플"""
    return ModelCatalog(
        id=1,
        alias="gpt-4o-mini",
        model_name="gpt-4o-mini",
        provider="openai",
        model_type="llm",
        role_mask=0b111,  # 모든 역할 허용
        price_per_input_token=0.15,
        price_per_output_token=0.6,
        price_currency="USD",
        input_token_weight=1.0,
        output_token_weight=4.0,
        status="active",
        version="2024-07-18",
        description="OpenAI GPT-4o Mini model"
    )


@pytest.fixture
def sample_claude3_haiku():
    """Claude-3-Haiku 모델 샘플"""
    return ModelCatalog(
        id=2,
        alias="claude-3-haiku",
        model_name="claude-3-haiku-20240307",
        provider="anthropic",
        model_type="llm",
        role_mask=0b111,  # 모든 역할 허용
        price_per_input_token=0.25,
        price_per_output_token=1.25,
        price_currency="USD",
        input_token_weight=1.0,
        output_token_weight=5.0,
        status="active",
        version="20240307",
        description="Anthropic Claude-3 Haiku model"
    )


@pytest.fixture
def sample_board_policy(sample_board_id):
    """보드 정책 샘플"""
    return BoardModelPolicy(
        id=1,
        board_id=sample_board_id,
        allowed_models=["gpt-4o-mini", "claude-3-haiku"],
        default_model="gpt-4o-mini",
        budget_limit_wtu=10000,
        budget_period="monthly",
        is_active=True
    )


@pytest.fixture
def sample_user_policy(sample_board_id, sample_user_id):
    """사용자 정책 샘플"""
    return UserModelPolicy(
        id=1,
        board_id=sample_board_id,
        user_id=sample_user_id,
        allowed_models=["gpt-4o-mini"],
        default_model="gpt-4o-mini",
        budget_limit_wtu=5000,
        budget_period="monthly",
        is_active=True
    )


@pytest.fixture
def mock_openai_service():
    """OpenAI 서비스 Mock"""
    with patch('app.ai.openai_service.openai_service') as mock:
        # 응답 Mock 설정
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message.content = "Mock AI response"
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 100
        
        mock.client.chat.completions.create.return_value = mock_response
        yield mock


@pytest.fixture
def mock_count_tokens():
    """토큰 카운트 함수 Mock"""
    with patch('app.metrics.count_tokens') as mock:
        mock.return_value = 50  # 기본값
        yield mock


@pytest.fixture
def mock_usage_recorder():
    """사용량 기록기 Mock"""
    with patch('app.metrics.usage_recorder_v2.record_usage') as mock:
        mock_record = AsyncMock()
        mock_record.wtu = 250
        mock_record.in_tokens = 50
        mock_record.out_tokens = 100
        mock.return_value = mock_record
        yield mock


@pytest.fixture
def mock_monthly_wtu():
    """월간 WTU 조회 Mock"""
    with patch('app.metrics.usage_recorder_v2.get_board_total_monthly_wtu') as mock:
        mock.return_value = 3000  # 현재 월 사용량
        yield mock


# 통합 테스트용 복합 픽스처
@pytest.fixture
def full_model_setup(
    sample_gpt4o_mini,
    sample_claude3_haiku,
    sample_board_policy,
    sample_user_policy,
    mock_openai_service,
    mock_count_tokens,
    mock_usage_recorder,
    mock_monthly_wtu
):
    """전체 모델 피커 설정"""
    return {
        "models": [sample_gpt4o_mini, sample_claude3_haiku],
        "board_policy": sample_board_policy,
        "user_policy": sample_user_policy,
        "mocks": {
            "openai": mock_openai_service,
            "tokens": mock_count_tokens,
            "usage": mock_usage_recorder,
            "monthly_wtu": mock_monthly_wtu
        }
    }


# 마커 등록
def pytest_configure(config):
    """pytest 설정"""
    config.addinivalue_line("markers", "unit: 단위 테스트")
    config.addinivalue_line("markers", "integration: 통합 테스트")
    config.addinivalue_line("markers", "acceptance: 수용 테스트")
    config.addinivalue_line("markers", "slow: 느린 테스트")


# 테스트 클래스별 공통 설정
@pytest.fixture(autouse=True)
def setup_test_environment():
    """테스트 환경 자동 설정"""
    # 로깅 레벨 조정
    import logging
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    # 환경 변수 설정
    import os
    os.environ["TESTING"] = "1"
    
    yield
    
    # 정리
    if "TESTING" in os.environ:
        del os.environ["TESTING"]
