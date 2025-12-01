"""마이그레이션 자동 실행 유틸리티

서버 시작 시 Alembic 마이그레이션을 자동으로 확인하고 업데이트합니다.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def get_alembic_config() -> Config:
    """Alembic 설정 객체 반환"""
    # 프로젝트 루트 경로
    project_root = Path(__file__).resolve().parents[2]
    alembic_ini_path = project_root / "alembic.ini"

    config = Config(str(alembic_ini_path))
    config.set_main_option("script_location", str(project_root / "migrations"))

    # async URL을 sync URL로 변환 (alembic은 sync 연결 사용)
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace(
        "postgresql+asyncpg", "postgresql"
    )
    config.set_main_option("sqlalchemy.url", sync_url)

    return config


def get_current_revision() -> str | None:
    """현재 데이터베이스의 마이그레이션 버전 조회"""
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace(
        "postgresql+asyncpg", "postgresql"
    )

    try:
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            rev = context.get_current_revision()
            return str(rev) if rev else None
    except Exception as e:
        logger.warning(f"현재 마이그레이션 버전 조회 실패: {e}")
        return None


def get_head_revision() -> str | None:
    """최신 마이그레이션 버전 조회"""
    config = get_alembic_config()
    script = ScriptDirectory.from_config(config)
    head = script.get_current_head()
    return str(head) if head else None


def check_migration_status() -> dict:
    """마이그레이션 상태 확인

    Returns:
        dict: current (현재 버전), head (최신 버전), is_up_to_date (최신 여부)
    """
    current = get_current_revision()
    head = get_head_revision()

    return {
        "current": current,
        "head": head,
        "is_up_to_date": current == head,
    }


def run_migrations() -> bool:
    """마이그레이션 실행

    Returns:
        bool: 성공 여부
    """
    try:
        config = get_alembic_config()

        # 마이그레이션 상태 확인
        status = check_migration_status()

        if status["is_up_to_date"]:
            logger.info(f"✅ 마이그레이션이 최신 상태입니다 (revision: {status['current']})")
            return True

        logger.info(
            f"🔄 마이그레이션 업데이트 중... ({status['current']} → {status['head']})"
        )

        # 마이그레이션 실행
        command.upgrade(config, "head")

        logger.info(f"✅ 마이그레이션 완료 (revision: {status['head']})")
        return True

    except Exception as e:
        logger.error(f"❌ 마이그레이션 실행 실패: {e}")
        return False


def run_migrations_on_startup(auto_migrate: bool = True) -> None:
    """서버 시작 시 마이그레이션 확인 및 실행

    Args:
        auto_migrate: True면 자동 마이그레이션, False면 상태만 확인
    """
    try:
        status = check_migration_status()

        if status["current"] is None:
            logger.warning("⚠️ 데이터베이스에 마이그레이션 기록이 없습니다. 초기 마이그레이션이 필요합니다.")
            if auto_migrate:
                run_migrations()
            return

        if not status["is_up_to_date"]:
            logger.warning(
                f"⚠️ 마이그레이션이 최신 상태가 아닙니다. "
                f"(현재: {status['current']}, 최신: {status['head']})"
            )
            if auto_migrate:
                run_migrations()
        else:
            logger.info(f"✅ 마이그레이션 상태: 최신 (revision: {status['current']})")

    except Exception as e:
        logger.error(f"❌ 마이그레이션 상태 확인 실패: {e}")
        # 마이그레이션 실패해도 서버는 시작 (개발 환경 등을 위해)
        if not settings.is_production:
            logger.warning("⚠️ 개발 환경이므로 서버를 계속 시작합니다.")
        else:
            raise RuntimeError("프로덕션 환경에서 마이그레이션 확인 실패") from e
