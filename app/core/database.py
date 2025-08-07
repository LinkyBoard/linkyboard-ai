import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from dotenv import load_dotenv

load_dotenv()

# 환경 변수에서 데이터베이스 설정 읽기
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")

# 데이터베이스 URL 구성
DATABASE_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
SYNC_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# 비동기 엔진 생성
async_engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "0")),
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "3600")),
)

# 동기 엔진 (Alembic용)
sync_engine = create_engine(
    SYNC_DATABASE_URL,
    echo=True,
    pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "0")),
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "3600")),
)

# 세션 생성
AsyncSessionLocal = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

# Base 클래스 생성
Base = declarative_base()


# 데이터베이스 세션 의존성
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
