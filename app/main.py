from fastapi import FastAPI
from app.collect.v1.clipper.router import router as clipper_router
from app.user.v1.router import router as user_router
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

@app.get("/")
def read_root():
    return {"Hello": "World"}
