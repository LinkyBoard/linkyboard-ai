from fastapi import FastAPI
from app.collect.v1.clipper.router import router as clipper_router
from app.user.v1.router import router as user_router
from app.recommendation.v1.router import router as recommendation_router
from app.with_ai.router import router as with_ai_router
from app.admin.models.router import router as admin_models_router
from app.board.model_policy.router import router as board_model_policy_router
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

# User
app.include_router(user_router)

# Recommendation
app.include_router(recommendation_router)

# With AI (모델 선택 지원)
app.include_router(with_ai_router)

# Admin - Model Management
app.include_router(admin_models_router)

# Board - Model Policy
app.include_router(board_model_policy_router)

@app.get("/")
def read_root():
    return {"Hello": "World"}
