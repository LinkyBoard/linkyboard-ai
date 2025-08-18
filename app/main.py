from fastapi import FastAPI
from app.collect.v1.clipper.router import router as clipper_router
from app.collect.v1.content.router import router as content_router
from app.board_ai.router import router as board_ai_router
from app.user_sync.router import router as user_sync_router
from app.admin.models.router import router as admin_models_router
from app.core.middleware import LoggingMiddleware, ErrorHandlingMiddleware
from app.core.logging import log, setup_logging
from app.core.database import get_sync_db
from app.core.model_catalog_init import ensure_model_catalog_initialized
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 생명주기 관리 - 시작/종료 시 실행할 작업"""
    # 로깅 시스템 초기화 (최우선)
    setup_logging()
    
    # 앱 시작 시 실행
    log.info("LinkyBoard AI 서비스 시작 중...")
    
    # 모델 카탈로그 초기화 확인
    try:
        with next(get_sync_db()) as db:
            ensure_model_catalog_initialized(db)
    except Exception as e:
        log.error(f"모델 카탈로그 초기화 실패: {e}")
    
    log.info("LinkyBoard AI 서비스가 시작되었습니다.")
    
    yield
    
    # 앱 종료 시 실행
    log.info("LinkyBoard AI 서비스가 종료됩니다.")

app = FastAPI(
    title="LinkyBoard AI API",
    description="링키보드 AI 서비스의 공식 문서",
    version="0.1.0",
    contact={"name": "Wonjun", "url": "https://github.com/wonjun0120"},
    lifespan=lifespan
)

# 미들웨어 추가
app.add_middleware(LoggingMiddleware)
app.add_middleware(ErrorHandlingMiddleware)

# Clipper
app.include_router(clipper_router)

# Items (아이템 관리)
app.include_router(content_router)

# Board AI (보드 문맥 기반 AI 작업)
app.include_router(board_ai_router)

# User Sync (Spring Boot 사용자 동기화)
app.include_router(user_sync_router)

# Admin - Model Management
app.include_router(admin_models_router)

@app.get("/")
def read_root():
    return {"Hello": "World"}
