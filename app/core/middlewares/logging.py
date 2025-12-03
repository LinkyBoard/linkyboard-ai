"""요청/응답 로깅 미들웨어"""

from typing import Callable, cast

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger
from app.core.middlewares.context import set_request_id
from app.core.utils.time import measure_time

logger = get_logger(__name__)

# 로깅 제외 경로
EXCLUDE_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico"}


class LoggingMiddleware(BaseHTTPMiddleware):
    """요청/응답 로깅 및 처리 시간 측정 미들웨어"""

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # 제외 경로 체크
        if request.url.path in EXCLUDE_PATHS:
            return cast(Response, await call_next(request))

        # 요청 ID 설정 (헤더에서 가져오거나 새로 생성)
        request_id = request.headers.get("X-Request-ID")
        request_id = set_request_id(request_id)

        # 요청 정보 로깅
        logger.info(
            f"[{request_id}] → {request.method} {request.url.path} "
            f"| Client: {request.client.host if request.client else 'unknown'}"
        )

        # 요청 처리 및 시간 측정
        with measure_time() as timer:
            try:
                response = await call_next(request)
            except Exception as e:
                # 예외 발생 시 로깅
                logger.error(
                    f"[{request_id}] ✗ {request.method} {request.url.path} "
                    f"| Error: {str(e)} | Time: {timer['elapsed_ms']:.2f}ms"
                )
                raise

        # 처리 시간
        process_time = timer["elapsed_ms"]

        # 응답 헤더에 요청 ID와 처리 시간 추가
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"

        # 응답 정보 로깅
        status_emoji = "✓" if response.status_code < 400 else "✗"
        log_method = (
            logger.info if response.status_code < 400 else logger.warning
        )

        log_method(
            f"[{request_id}] {status_emoji} {request.method} "
            f"{request.url.path} | Status: {response.status_code} "
            f"| Time: {process_time:.2f}ms"
        )

        return cast(Response, response)
