"""테스트 설정"""

import itertools
import os
from typing import Generator
from unittest.mock import patch

import pytest
import pytest_asyncio
from docker import from_env
from docker.errors import DockerException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.minio import MinioContainer
from testcontainers.postgres import PostgresContainer

from app.core.config import Settings, settings
from app.core.database import Base, get_db
from app.core.llm.types import LLMResult
from app.core.utils.datetime import now_utc
from app.main import app


def normalize_endpoint(endpoint: str) -> str:
    """endpoint URL에 프로토콜이 없으면 http:// 추가"""
    if not endpoint.startswith(("http://", "https://")):
        return f"http://{endpoint}"
    return endpoint


def _is_docker_available() -> bool:
    """로컬 환경에서 Docker 접근 가능 여부 확인"""
    if os.getenv("FORCE_DOCKER_TESTS", "").lower() in {"1", "true"}:
        return True
    if os.getenv("SKIP_DOCKER_TESTS", "").lower() in {"1", "true"}:
        return False

    try:
        client = from_env()
        client.ping()
        return True
    except DockerException:
        return False
    except Exception:
        return False


DOCKER_AVAILABLE = _is_docker_available()


@pytest.fixture(scope="session")
def user_id_factory():
    """
    테스트마다 겹치지 않는 PK를 만들기 위한 ID 팩토리.
    UTC 기준 현재 타임스탬프(ms)를 시작값으로 사용
    """
    start = int(now_utc().timestamp() * 1000) % 2_000_000_000
    counter = itertools.count(start=start)

    def _factory(n: int = 1):
        if n == 1:
            return next(counter)
        return [next(counter) for _ in range(n)]

    return _factory


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    """PostgreSQL 테스트 컨테이너 (pgvector 포함)"""
    if not DOCKER_AVAILABLE:
        pytest.skip("Docker is not available; skipping container-based tests.")

    with PostgresContainer("pgvector/pgvector:pg16") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def test_database_url(postgres_container: PostgresContainer) -> str:
    """테스트 데이터베이스 URL"""
    # asyncpg를 위한 URL 생성
    return str(
        postgres_container.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://"
        )
    )


@pytest_asyncio.fixture
async def setup_test_database(test_database_url: str):
    """테스트 데이터베이스 테이블 생성"""
    engine = create_async_engine(test_database_url, echo=False)
    async with engine.begin() as conn:
        # 이전 테스트 데이터 정리 후 새로 생성
        await conn.run_sync(Base.metadata.drop_all)
        # pgvector extension 활성화
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_database_url: str, setup_test_database):
    """테스트 데이터베이스 세션"""
    engine = create_async_engine(test_database_url, echo=False)

    # 각 테스트마다 깨끗한 스키마 유지
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()

    await engine.dispose()


# NOTE:
# pytest-asyncio(0.21+)는 기본적으로 테스트마다 독립적인 event loop를 생성
# session 스코프 async fixture는 이 구조와 충돌하여 ScopeMismatch 에러를 유발할 수 있음
# 이를 방지하기 위해 async fixture는 모두 function 스코프로 유지
@pytest_asyncio.fixture
async def client(db_session, minio_container: MinioContainer):
    """비동기 테스트 클라이언트 (테스트 DB 및 MinIO 사용)"""
    from app.core.storage import S3Client, _create_s3_client, get_s3_client

    # 테스트용 데이터베이스로 의존성 오버라이드
    async def override_get_db():
        yield db_session

    # lru_cache 초기화
    _create_s3_client.cache_clear()

    # MinIO 설정으로 테스트 S3 클라이언트 생성
    config = minio_container.get_config()
    endpoint = normalize_endpoint(config["endpoint"])

    test_settings = Settings(
        s3_endpoint=endpoint,
        s3_access_key=config["access_key"],
        s3_secret_key=config["secret_key"],
        s3_bucket_contents="test-contents",
        s3_region="us-east-1",
        s3_use_ssl=False,
    )

    test_s3_client = S3Client(test_settings)

    # 버킷이 이미 존재하면 무시
    try:
        test_s3_client.client.create_bucket(
            Bucket=test_settings.s3_bucket_contents
        )
    except (
        test_s3_client.client.exceptions.BucketAlreadyOwnedByYou,
        test_s3_client.client.exceptions.BucketAlreadyExists,
    ):
        # 버킷이 이미 존재하는 경우 무시하고 계속 진행
        pass

    # S3 클라이언트 의존성 오버라이드
    def override_get_s3_client() -> S3Client:
        return test_s3_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_s3_client] = override_get_s3_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        yield client

    # 정리
    app.dependency_overrides.clear()
    _create_s3_client.cache_clear()


@pytest.fixture
def anyio_backend():
    """anyio 백엔드 설정"""
    return "asyncio"


@pytest.fixture
def api_key_header():
    """Internal API Key 헤더"""
    return {"X-Internal-Api-Key": settings.internal_api_key}


@pytest.fixture(scope="session")
def minio_container() -> Generator[MinioContainer, None, None]:
    """MinIO 테스트 컨테이너"""
    if not DOCKER_AVAILABLE:
        pytest.skip("Docker is not available; skipping container-based tests.")

    with MinioContainer() as minio:
        yield minio


@pytest.fixture
def test_s3_client(minio_container: MinioContainer):
    """테스트용 S3 클라이언트 (MinIO 사용)"""
    from app.core.storage import S3Client, _create_s3_client

    # lru_cache 초기화
    _create_s3_client.cache_clear()

    # MinIO 설정으로 테스트 클라이언트 생성
    config = minio_container.get_config()
    endpoint = normalize_endpoint(config["endpoint"])

    test_settings = Settings(
        s3_endpoint=endpoint,
        s3_access_key=config["access_key"],
        s3_secret_key=config["secret_key"],
        s3_bucket_contents="test-contents",
        s3_region="us-east-1",
        s3_use_ssl=False,
    )

    client = S3Client(test_settings)

    # 테스트 버킷 생성 (이미 존재하면 무시)
    try:
        client.client.create_bucket(Bucket=test_settings.s3_bucket_contents)
    except (
        client.client.exceptions.BucketAlreadyOwnedByYou,
        client.client.exceptions.BucketAlreadyExists,
    ):
        # 버킷이 이미 존재하는 경우 무시하고 계속 진행
        pass

    yield client

    # cleanup: lru_cache 초기화
    _create_s3_client.cache_clear()


# AI 도메인 테스트 설정


def pytest_configure(config):
    """pytest marker 등록"""
    config.addinivalue_line("markers", "real_ai: 실제 AI API를 사용하는 테스트 (유료)")
    config.addinivalue_line("markers", "mock_ai: Mock AI를 사용하는 테스트 (무료)")


def is_real_ai_enabled() -> bool:
    """실제 AI 테스트 활성화 여부"""
    return os.getenv("ENABLE_REAL_AI_TESTS", "false").lower() == "true"


@pytest.fixture
def skip_if_no_real_ai():
    """실제 AI 테스트가 비활성화된 경우 스킵"""
    if not is_real_ai_enabled():
        pytest.skip("ENABLE_REAL_AI_TESTS=true 설정 필요")


@pytest.fixture(autouse=True)
def mock_llm_completion():
    """LLM completion Mock - 자동 적용"""
    from unittest.mock import AsyncMock

    mock = AsyncMock()

    async def default_side_effect(*args, **kwargs):
        return LLMResult(
            content="Mock summary content",
            model="mock-model",
            input_tokens=100,
            output_tokens=50,
            finish_reason="stop",
        )

    mock.side_effect = default_side_effect

    # call_with_fallback이 노출되는 모든 경로를 Mock
    with patch("app.core.llm.fallback.call_with_fallback", mock), patch(
        "app.core.llm.call_with_fallback", mock
    ), patch(
        "app.domains.ai.summarization.service.call_with_fallback", mock
    ), patch(
        "app.domains.topics.agents.summarizer.call_with_fallback", mock
    ), patch(
        "app.domains.topics.agents.writer.call_with_fallback", mock
    ):
        yield mock


@pytest.fixture(autouse=True)
def mock_embedding():
    """임베딩 생성 Mock - 자동 적용"""

    # 텍스트 임베딩(3072)와 태그/카테고리 임베딩(1536)을 구분
    async def mock_embedding_3072(_text):
        return [0.1] * 3072

    async def mock_embedding_1536(_text):
        return [0.1] * 1536

    # create_embedding이 사용되는 모든 경로를 Mock
    with patch(
        "app.core.llm.fallback.create_embedding",
        side_effect=mock_embedding_3072,
    ) as mock_llm, patch(
        "app.core.llm.create_embedding",
        side_effect=mock_embedding_3072,
    ), patch(
        "app.domains.ai.embedding.service.create_embedding",
        side_effect=mock_embedding_3072,
    ), patch(
        "app.domains.ai.search.service.create_embedding",
        side_effect=mock_embedding_3072,
    ), patch(
        "app.domains.ai.personalization.service.create_embedding",
        side_effect=mock_embedding_1536,
    ), patch(
        "app.domains.ai.personalization.repository.create_embedding",
        side_effect=mock_embedding_1536,
    ):
        yield mock_llm


@pytest.fixture
def mock_youtube_transcript():
    """YouTube 자막 Mock"""
    with patch(
        "youtube_transcript_api.YouTubeTranscriptApi.get_transcript"
    ) as mock:
        mock.return_value = [
            {"text": "Mock transcript line 1", "start": 0.0, "duration": 2.0},
            {"text": "Mock transcript line 2", "start": 2.0, "duration": 2.0},
            {"text": "Mock transcript line 3", "start": 4.0, "duration": 2.0},
        ]
        yield mock
