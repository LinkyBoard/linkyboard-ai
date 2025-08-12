import time
import uuid
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logging import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """API 요청/응답 로깅 미들웨어"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 요청 ID 생성
        request_id = str(uuid.uuid4())[:8]
        
        # 시작 시간
        start_time = time.time()
        
        # 요청 시작 로깅 (콘솔용 - 간단하게)
        logger.info(f"🚀 {request.method} {request.url.path} [{request_id}]")
        
        # 요청 정보 로깅 (파일용 - 상세하게)
        logger.bind(
            api=True,
            request_id=request_id,
            method=request.method,
            url=str(request.url),
            client_ip=request.client.host if request.client else "unknown",
            log_type="request_start"
        ).info(f"Request started: {request.method} {request.url.path}")
        
        try:
            # 요청 처리
            response = await call_next(request)
            
            # 처리 시간 계산
            duration = round((time.time() - start_time) * 1000, 2)
            
            # 응답 완료 로깅 (콘솔용)
            status_emoji = "✅" if response.status_code < 400 else "❌"
            logger.info(f"{status_emoji} {request.method} {request.url.path} [{request_id}] {response.status_code} ({duration}ms)")
            
            # 응답 정보 로깅 (파일용)
            logger.bind(
                api=True,
                request_id=request_id,
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                duration=duration,
                log_type="request_end"
            ).info(f"Request completed: {response.status_code}")
            
            return response
            
        except Exception as e:
            # 에러 처리 시간 계산
            duration = round((time.time() - start_time) * 1000, 2)
            
            # 에러 로깅 (콘솔용)
            logger.error(f"💥 {request.method} {request.url.path} [{request_id}] ERROR ({duration}ms): {str(e)}")
            
            # 에러 로깅 (파일용)
            logger.bind(
                api=True,
                request_id=request_id,
                method=request.method,
                url=str(request.url),
                status_code=500,
                duration=duration,
                log_type="request_error"
            ).error(f"Request failed: {str(e)}")
            
            # 에러 응답 반환
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "request_id": request_id}
            )


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """전역 에러 처리 미들웨어"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except Exception as e:
            logger.exception(f"Unhandled exception: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )
