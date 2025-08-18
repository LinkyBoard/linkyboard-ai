from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings

# 비동기 엔진 생성
async_engine = create_async_engine(
    settings.database_url,
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,  # 연결 상태 확인
    pool_reset_on_return='commit',  # 연결 반환 시 커밋
)

# 동기 엔진 (Alembic용)
sync_engine = create_engine(
    settings.sync_database_url,
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
)

# 세션 생성
AsyncSessionLocal = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

# 동기 세션 (초기화용)
SyncSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=sync_engine
)

# Base 클래스 생성
Base = declarative_base()


# 데이터베이스 세션 의존성
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

# 동기 데이터베이스 세션 (앱 초기화용)
def get_sync_db():
    db = SyncSessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
