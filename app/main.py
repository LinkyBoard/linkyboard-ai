from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router as api_v1_router
from app.core.config import settings
from app.core.database import close_db
from app.core.exceptions import (
    BaseAPIException,
    base_exception_handler,
    generic_exception_handler,
    http_exception_handler,
)
from app.core.logging import get_logger, setup_logging
from app.core.middlewares import LoggingMiddleware
from app.core.migration import run_migrations_on_startup
from app.core.schemas import APIResponse

# 로깅 설정 초기화
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    # Startup
    logger.info(f"🚀 Starting {settings.app_name}...")

    # 마이그레이션 확인 및 자동 업데이트
    run_migrations_on_startup(auto_migrate=settings.auto_migrate)

    yield
    # Shutdown
    logger.info(f"👋 Shutting down {settings.app_name}...")
    await close_db()


def create_app() -> FastAPI:
    """FastAPI 애플리케이션 팩토리"""
    app = FastAPI(
        title=settings.app_name,
        description="FastAPI Domain-Driven Design Project Template",
        version="0.1.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )

    # 미들웨어 설정 (순서 중요: 아래에서 위로 실행됨)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(LoggingMiddleware)

    # 예외 핸들러 등록
    app.add_exception_handler(BaseAPIException, base_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # API 라우터 등록 (버저닝)
    app.include_router(api_v1_router, prefix="/api/v1")

    return app


app = create_app()


@app.get(
    "/health", tags=["Health"], response_model=APIResponse[dict[str, Any]]
)
async def health_check():
    """헬스 체크 엔드포인트"""
    return APIResponse(
        success=True,
        message="OK",
        data={
            "status": "healthy",
            "app_name": settings.app_name,
            "environment": settings.app_env,
        },
    )
