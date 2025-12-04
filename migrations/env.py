"""Alembic 환경 설정"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402

# 모든 모델 임포트 (마이그레이션 감지를 위해)
from app.domains.users.models import User  # noqa: F401, E402
from app.domains.contents.models import Content  # noqa: F401, E402
from app.domains.ai.models import (  # noqa: F401, E402
    Category,
    ChunkStrategy,
    ContentEmbeddingMetadata,
    SummaryCache,
    Tag,
    UserCategoryUsage,
    UserTagUsage,
)

# Alembic Config 객체
config = context.config

# 로깅 설정
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 메타데이터 설정
target_metadata = Base.metadata

# 데이터베이스 URL 설정 (async → sync 변환)
sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
config.set_main_option("sqlalchemy.url", sync_url)


def run_migrations_offline() -> None:
    """오프라인 모드로 마이그레이션 실행.

    이 모드에서는 DBAPI 연결 없이 'URL' 만으로 컨텍스트를 구성합니다.
    SQL을 직접 스크립트로 출력합니다.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """온라인 모드로 마이그레이션 실행.

    이 모드에서는 데이터베이스에 연결하여 마이그레이션을 실행합니다.
    """
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
