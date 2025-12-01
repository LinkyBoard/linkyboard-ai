"""전역 로깅 설정"""

import logging
import sys

from app.core.config import settings


class ColoredFormatter(logging.Formatter):
    """컬러 로그 포맷터 (개발 환경용)"""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging() -> None:
    """애플리케이션 로깅 설정"""

    # 로그 레벨 설정
    log_level = logging.DEBUG if settings.debug else logging.INFO

    # 로그 포맷 설정
    if settings.is_development:
        # 개발 환경: 컬러 + 상세 정보
        log_fmt = (
            "%(asctime)s | %(levelname)-8s | "
            "%(name)s:%(lineno)d | %(message)s"
        )
        formatter: logging.Formatter = ColoredFormatter(
            fmt=log_fmt,
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        # 프로덕션 환경: JSON 형식 (로그 수집 시스템 연동 용이)
        json_fmt = (
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"logger": "%(name)s", "message": "%(message)s"}'
        )
        formatter = logging.Formatter(
            fmt=json_fmt,
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )

    # 핸들러 설정
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(log_level)

    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # 외부 라이브러리 로그 레벨 조정
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.database_echo else logging.WARNING
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """로거 인스턴스 반환

    Args:
        name: 로거 이름 (보통 __name__ 사용)

    Returns:
        logging.Logger: 설정된 로거 인스턴스

    Example::

        from app.core.logging import get_logger
        logger = get_logger(__name__)
        logger.info("Hello, World!")
    """
    return logging.getLogger(name)
