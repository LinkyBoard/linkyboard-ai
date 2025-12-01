"""API v1 라우터"""

from typing import Any

from fastapi import APIRouter

from app.core.schemas import APIResponse
from app.domains.users.router import router as users_router

api_router = APIRouter()

# 도메인 라우터 등록
api_router.include_router(users_router, prefix="/users", tags=["Users"])


@api_router.get("/", response_model=APIResponse[dict[str, Any]])
async def api_v1_root():
    """API v1 루트 엔드포인트"""
    return APIResponse(
        success=True,
        message="FastAPI DDD Template API v1",
        data={
            "version": "1.0.0",
            "docs": "/docs",
        },
    )
