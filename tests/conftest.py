import pytest
import pytest_asyncio
import os, sys, pathlib
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_USER", "user")
os.environ.setdefault("POSTGRES_PASSWORD", "pass")
os.environ.setdefault("POSTGRES_DB", "test_db")
os.environ.setdefault("OPENAI_API_KEY", "test")

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from app.core.database import Base


@pytest_asyncio.fixture
async def db_session(tmp_path) -> AsyncSession:
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    engine = create_async_engine(db_url, future=True)

    # remove duplicate index definitions
    for table in Base.metadata.tables.values():
        seen = set()
        for idx in list(table.indexes):
            if idx.name in seen:
                table.indexes.remove(idx)
            else:
                seen.add(idx.name)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with async_session() as session:
            yield session
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
