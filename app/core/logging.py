import os
import sys
from pathlib import Path
from loguru import logger
from app.core.config import settings


def api_filter(record):
    """API 로그 필터링 함수"""
    return "api" in record["extra"]


def api_formatter(record):
    """API 로그 포맷터"""
    extra = record["extra"]
    log_type = extra.get("log_type", "unknown")
    
    base_info = f"{record['time']:YYYY-MM-DD HH:mm:ss} | {extra.get('request_id', 'N/A')} | {extra.get('method', 'N/A')} {extra.get('url', 'N/A')}"
    
    if log_type == "request_start":
        return f"{base_info} | START | {record['message']}\n"
    elif log_type in ["request_end", "request_error"]:
        return f"{base_info} | {extra.get('status_code', 'N/A')} | {extra.get('duration', 'N/A')}ms | {record['message']}\n"
    else:
        return f"{base_info} | {record['message']}\n"


def setup_logging():
    """Loguru 로깅 설정"""
    
    # 기본 핸들러 제거
    logger.remove()
    
    # 로그 디렉토리 생성
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(exist_ok=True)
    
    # 콘솔 로깅 설정 (항상 활성화)
    if settings.DEBUG:
        # 개발 환경 - 상세한 콘솔 로그
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
            level=settings.LOG_LEVEL,
            colorize=True,
            backtrace=True,
            diagnose=True
        )
    else:
        # 프로덕션 환경 - 간단한 콘솔 로그 (INFO 이상)
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
            level="INFO",
            colorize=True
        )
    
    # API 요청 전용 콘솔 로깅 (색상으로 구분)
    logger.add(
        sys.stderr,
        format="<blue>{time:HH:mm:ss}</blue> | <yellow>API</yellow> | <cyan>{extra[request_id]}</cyan> | <magenta>{extra[method]}</magenta> <white>{extra[url]}</white> | <green>{extra[status_code]}</green> | <yellow>{extra[duration]}ms</yellow> | {message}",
        level="INFO",
        colorize=True,
        filter=lambda record: "api" in record["extra"] and record["extra"].get("log_type") == "request_end"
    )
    
    # API 에러 전용 콘솔 로깅
    logger.add(
        sys.stderr,
        format="<blue>{time:HH:mm:ss}</blue> | <red>API ERROR</red> | <cyan>{extra[request_id]}</cyan> | <magenta>{extra[method]}</magenta> <white>{extra[url]}</white> | <red>{extra[status_code]}</red> | <yellow>{extra[duration]}ms</yellow> | <red>{message}</red>",
        level="ERROR",
        colorize=True,
        filter=lambda record: "api" in record["extra"] and record["extra"].get("log_type") == "request_error"
    )
    
    # 파일 로깅 설정
    # 일반 로그
    logger.add(
        log_dir / "app.log",
        format=settings.LOG_FORMAT,
        level=settings.LOG_LEVEL,
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
        enqueue=True,
        backtrace=True,
        diagnose=True
    )
    
    # 에러 로그 (ERROR 이상만)
    logger.add(
        log_dir / "error.log",
        format=settings.LOG_FORMAT,
        level="ERROR",
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
        enqueue=True,
        backtrace=True,
        diagnose=True
    )
    
    # API 접근 로그 (커스텀 포맷터 사용)
    logger.add(
        log_dir / "api.log",
        format=api_formatter,
        level="INFO",
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
        enqueue=True,
        filter=api_filter
    )
    
    # 데이터베이스 로그
    logger.add(
        log_dir / "database.log",
        format=settings.LOG_FORMAT,
        level="INFO",
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
        enqueue=True,
        filter=lambda record: "database" in record["extra"]
    )
    
    # OpenAI API 로그
    logger.add(
        log_dir / "ai.log",
        format=settings.LOG_FORMAT,
        level="INFO",
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
        enqueue=True,
        filter=lambda record: "ai" in record["extra"]
    )
    
    return logger


def get_logger(name: str = None):
    """로거 인스턴스 반환"""
    if name:
        return logger.bind(name=name)
    return logger


# 로깅 설정 초기화
setup_logging()

# 기본 로거 인스턴스
log = get_logger("linkyboard-ai")
