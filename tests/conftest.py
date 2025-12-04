"""테스트 설정"""

import itertools
from typing import Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.minio import MinioContainer
from testcontainers.postgres import PostgresContainer

from app.core.config import Settings, settings
from app.core.database import Base, get_db
from app.core.utils.datetime import now_utc
from app.main import app


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
    """PostgreSQL 테스트 컨테이너"""
    with PostgresContainer("postgres:16-alpine") as postgres:
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
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_database_url: str, setup_test_database):
    """테스트 데이터베이스 세션"""
    engine = create_async_engine(test_database_url, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
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
    endpoint = config["endpoint"]
    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"http://{endpoint}"

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
    except test_s3_client.client.exceptions.BucketAlreadyOwnedByYou:
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
    endpoint = config["endpoint"]
    # boto3는 프로토콜이 필요함
    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"http://{endpoint}"

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
    except client.client.exceptions.BucketAlreadyOwnedByYou:
        pass

    yield client

    # cleanup: lru_cache 초기화
    _create_s3_client.cache_clear()
