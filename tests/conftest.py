"""테스트 설정"""

import itertools
from typing import Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.utils.datetime import now_utc
from app.main import app


@pytest.fixture(scope="session")
def user_id_factory():
    """
    테스트마다 겹치지 않는 PK를 만들기 위한 ID 팩토리.
    UTC 기준 현재 타임스탬프(ms)를 시작값으로 사용
    """
    start = int(now_utc().timestamp())
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


@pytest_asyncio.fixture(scope="session")
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


@pytest_asyncio.fixture
async def client(db_session):
    """비동기 테스트 클라이언트 (테스트 DB 사용)"""

    # 테스트용 데이터베이스로 의존성 오버라이드
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        yield client

    # 정리
    app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend():
    """anyio 백엔드 설정"""
    return "asyncio"


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop for async fixtures"""
    import asyncio

    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def api_key_header():
    """Internal API Key 헤더"""
    return {"X-Internal-Api-Key": settings.internal_api_key}
