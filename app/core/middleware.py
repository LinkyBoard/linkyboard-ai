import time
import uuid
import json
from datetime import date
from typing import Callable
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.database import AsyncSessionLocal
from app.metrics.token_quota_service import (
    check_token_availability, 
    consume_tokens, 
    InsufficientTokensError,
    get_or_create_user_quota
)
from app.metrics.token_counter import estimate_tokens

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


class TokenQuotaMiddleware(BaseHTTPMiddleware):
    """토큰 쿼터 검증 및 사용량 추적 미들웨어"""
    
    def __init__(self, app):
        super().__init__(app)
        # AI 처리가 필요한 엔드포인트들
        self.ai_endpoints = [
            "/api/v1/agents/",
            "/api/v1/board-ai/",
            "/api/v1/collect/v1/clipper/",
            "/api/v1/embedding/",
            "/api/v1/ai/",
            "/audio/",
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # AI 엔드포인트인지 확인
        if not self._is_ai_endpoint(request.url.path):
            return await call_next(request)
        
        # 사용자 ID 추출
        user_id = self._extract_user_id(request)
        if not user_id:
            # 사용자 ID가 없으면 통과 (인증은 다른 미들웨어에서 처리)
            return await call_next(request)
        
        # 요청 본문 읽기 (토큰 추정용)
        body = await self._get_request_body(request)
        estimated_tokens = self._estimate_request_tokens(request, body)
        
        # 토큰 쿼터 검증
        try:
            async with AsyncSessionLocal() as session:
                if not await check_token_availability(user_id, estimated_tokens, session=session):
                    # 쿼터 부족
                    quota_info = await get_or_create_user_quota(user_id, session=session)
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={
                            "error": "토큰 할당량이 부족합니다",
                            "code": "INSUFFICIENT_TOKENS",
                            "required_tokens": estimated_tokens,
                            "available_tokens": quota_info.remaining_tokens,
                            "total_quota": quota_info.allocated_quota,
                            "used_tokens": quota_info.used_tokens
                        }
                    )
        except Exception as e:
            logger.error(f"Token quota check failed: {e}")
            # 에러 시 통과 (서비스 중단 방지)
            return await call_next(request)
        
        # 요청 처리
        response = await call_next(request)
        
        # 응답 완료 후 실제 토큰 소비 처리
        if response.status_code == 200:
            try:
                async with AsyncSessionLocal() as session:
                    await consume_tokens(user_id, estimated_tokens, session=session)
                    logger.info(f"Consumed {estimated_tokens} tokens for user {user_id}")
            except InsufficientTokensError as e:
                logger.warning(f"Token consumption failed after request: {e}")
            except Exception as e:
                logger.error(f"Failed to consume tokens: {e}")
        
        return response
    
    def _is_ai_endpoint(self, path: str) -> bool:
        """AI 처리가 필요한 엔드포인트인지 확인"""
        return any(ai_endpoint in path for ai_endpoint in self.ai_endpoints)
    
    def _extract_user_id(self, request: Request) -> int:
        """요청에서 사용자 ID 추출"""
        # 헤더에서 직접 추출
        user_id = request.headers.get("x-user-id")
        if user_id:
            try:
                return int(user_id)
            except ValueError:
                pass
        
        # 쿼리 파라미터에서 추출
        user_id = request.query_params.get("user_id")
        if user_id:
            try:
                return int(user_id)
            except ValueError:
                pass
        
        return None
    
    async def _get_request_body(self, request: Request) -> str:
        """요청 본문 읽기"""
        try:
            body = await request.body()
            return body.decode('utf-8') if body else ""
        except Exception as e:
            logger.warning(f"Failed to read request body: {e}")
            return ""
    
    def _estimate_request_tokens(self, request: Request, body: str) -> int:
        """요청에서 예상 토큰 수 계산"""
        try:
            # 기본 토큰 수 (최소값)
            base_tokens = 100
            
            # 요청 본문 크기 기반 추정
            if body:
                try:
                    # JSON 파싱 시도
                    json_data = json.loads(body)
                    # 주요 텍스트 필드에서 토큰 추정
                    text_content = ""
                    for key in ["content", "text", "message", "prompt", "description", "summary"]:
                        if key in json_data and isinstance(json_data[key], str):
                            text_content += json_data[key] + " "
                    
                    if text_content:
                        estimated = estimate_tokens(text_content.strip())
                        return max(base_tokens, estimated)
                except json.JSONDecodeError:
                    # JSON이 아니면 텍스트로 추정
                    estimated = estimate_tokens(body)
                    return max(base_tokens, estimated)
            
            # 엔드포인트별 기본 토큰 수
            path = request.url.path
            if "/board-ai/" in path:
                return 500  # 보드 분석은 더 많은 토큰 필요
            elif "/agents/" in path:
                return 300  # 에이전트 처리
            elif "/clipper/" in path:
                return 200  # 콘텐츠 추출
            elif "/embedding/" in path:
                return 150  # 임베딩 생성
            
            return base_tokens
            
        except Exception as e:
            logger.warning(f"Token estimation failed: {e}")
            return 100  # 기본값


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


async def token_quota_dependency(request: Request):
    """
    의존성 주입용 토큰 쿼터 검증 함수
    FastAPI 라우터에서 직접 사용 가능
    """
    user_id = request.headers.get("x-user-id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자 ID가 필요합니다"
        )
    
    try:
        user_id = int(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="올바른 사용자 ID가 아닙니다"
        )
    
    # 기본 토큰 수 요구
    required_tokens = 100
    
    async with AsyncSessionLocal() as session:
        if not await check_token_availability(user_id, required_tokens, session=session):
            quota_info = await get_or_create_user_quota(user_id, session=session)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "토큰 할당량이 부족합니다",
                    "code": "INSUFFICIENT_TOKENS",
                    "available_tokens": quota_info.remaining_tokens,
                    "total_quota": quota_info.allocated_quota
                }
            )
    
    return user_id
