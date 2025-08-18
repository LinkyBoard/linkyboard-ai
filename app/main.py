from fastapi import FastAPI
from app.collect.v1.clipper.router import router as clipper_router
from app.collect.v1.content.router import router as content_router
from app.board_ai.router import router as board_ai_router
from app.user_sync.router import router as user_sync_router
from app.admin.models.router import router as admin_models_router
from app.core.middleware import LoggingMiddleware, ErrorHandlingMiddleware
from app.core.logging import log

app = FastAPI(
    title="LinkyBoard AI API",
    description="링키보드 AI 서비스의 공식 문서",
    version="0.1.0",
    contact={"name": "Wonjun", "url": "https://github.com/wonjun0120"}
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
