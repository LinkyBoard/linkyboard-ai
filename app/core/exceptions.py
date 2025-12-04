from enum import Enum
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


class ErrorCode(str, Enum):
    """전역 에러 코드"""

    # 공통 에러
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    BAD_REQUEST = "BAD_REQUEST"
    CONFLICT = "CONFLICT"

    # 인증 관련
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"

    # LLM 관련
    LLM_PROVIDER_ERROR = "LLM_PROVIDER_ERROR"
    ALL_PROVIDERS_FAILED = "ALL_PROVIDERS_FAILED"
    INVALID_MODEL_TIER = "INVALID_MODEL_TIER"

    # Storage 관련
    STORAGE_ERROR = "STORAGE_ERROR"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    S3_UPLOAD_FAILED = "S3_UPLOAD_FAILED"
    S3_DOWNLOAD_FAILED = "S3_DOWNLOAD_FAILED"


class BaseAPIException(HTTPException):
    """기본 API 예외 클래스"""

    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        detail: Optional[Dict[str, Any]] = None,
    ):
        self.error_code = error_code
        self.message = message
        self.detail_info = detail or {}
        super().__init__(status_code=status_code, detail=message)


class BadRequestException(BaseAPIException):
    """400 Bad Request"""

    def __init__(
        self,
        message: str = "잘못된 요청입니다.",
        error_code: str = ErrorCode.BAD_REQUEST,
        detail: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            message=message,
            detail=detail,
        )


class UnauthorizedException(BaseAPIException):
    """401 Unauthorized"""

    def __init__(
        self,
        message: str = "인증이 필요합니다.",
        error_code: str = ErrorCode.UNAUTHORIZED,
        detail: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=error_code,
            message=message,
            detail=detail,
        )


class ForbiddenException(BaseAPIException):
    """403 Forbidden"""

    def __init__(
        self,
        message: str = "접근 권한이 없습니다.",
        error_code: str = ErrorCode.FORBIDDEN,
        detail: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code=error_code,
            message=message,
            detail=detail,
        )


class NotFoundException(BaseAPIException):
    """404 Not Found"""

    def __init__(
        self,
        message: str = "리소스를 찾을 수 없습니다.",
        error_code: str = ErrorCode.NOT_FOUND,
        detail: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=error_code,
            message=message,
            detail=detail,
        )


class ConflictException(BaseAPIException):
    """409 Conflict"""

    def __init__(
        self,
        message: str = "리소스 충돌이 발생했습니다.",
        error_code: str = ErrorCode.CONFLICT,
        detail: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code=error_code,
            message=message,
            detail=detail,
        )


class InternalServerException(BaseAPIException):
    """500 Internal Server Error"""

    def __init__(
        self,
        message: str = "서버 내부 오류가 발생했습니다.",
        error_code: str = ErrorCode.INTERNAL_ERROR,
        detail: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=error_code,
            message=message,
            detail=detail,
        )


class StorageException(InternalServerException):
    """Storage 관련 예외"""

    def __init__(
        self,
        message: str = "파일 저장소 오류가 발생했습니다.",
        error_code: str = ErrorCode.STORAGE_ERROR,
        detail: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            detail=detail,
        )


async def base_exception_handler(
    request: Request, exc: BaseAPIException
) -> JSONResponse:
    """BaseAPIException 핸들러"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.message,
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "detail": exc.detail_info,
            },
        },
    )


async def http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
    """HTTPException 핸들러"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": str(exc.detail),
            "error": {
                "code": ErrorCode.INTERNAL_ERROR,
                "message": str(exc.detail),
                "detail": None,
            },
        },
    )


async def generic_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """일반 예외 핸들러"""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "서버 내부 오류가 발생했습니다.",
            "error": {
                "code": ErrorCode.INTERNAL_ERROR,
                "message": "서버 내부 오류가 발생했습니다.",
                "detail": None,
            },
        },
    )
