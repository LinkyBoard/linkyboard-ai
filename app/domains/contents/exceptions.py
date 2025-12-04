"""Contents 도메인 예외 정의"""

from enum import Enum

from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)


class ContentErrorCode(str, Enum):
    """콘텐츠 도메인 에러 코드"""

    CONTENT_NOT_FOUND = "CONTENT_NOT_FOUND"
    CONTENT_ALREADY_DELETED = "CONTENT_ALREADY_DELETED"
    INVALID_CONTENT_TYPE = "INVALID_CONTENT_TYPE"
    FILE_SIZE_EXCEEDED = "FILE_SIZE_EXCEEDED"
    CACHE_NOT_FOUND = "CACHE_NOT_FOUND"


class ContentNotFoundException(NotFoundException):
    """콘텐츠를 찾을 수 없는 경우"""

    def __init__(self, content_id: int | None = None):
        detail = {"content_id": content_id} if content_id else {}
        super().__init__(
            message="콘텐츠를 찾을 수 없습니다.",
            error_code=ContentErrorCode.CONTENT_NOT_FOUND,
            detail=detail,
        )


class ContentAlreadyDeletedException(ForbiddenException):
    """이미 삭제된 콘텐츠인 경우"""

    def __init__(self, content_id: int | None = None):
        detail = {"content_id": content_id} if content_id else {}
        super().__init__(
            message="이미 삭제된 콘텐츠입니다.",
            error_code=ContentErrorCode.CONTENT_ALREADY_DELETED,
            detail=detail,
        )


class InvalidContentTypeException(BadRequestException):
    """유효하지 않은 콘텐츠 타입인 경우"""

    def __init__(self, content_type: str | None = None):
        detail = {"content_type": content_type} if content_type else {}
        super().__init__(
            message="유효하지 않은 콘텐츠 타입입니다.",
            error_code=ContentErrorCode.INVALID_CONTENT_TYPE,
            detail=detail,
        )


class FileSizeExceededException(BadRequestException):
    """파일 크기가 제한을 초과한 경우"""

    def __init__(
        self, file_size: int | None = None, max_size: int | None = None
    ):
        detail = {}
        if file_size:
            detail["file_size"] = file_size
        if max_size:
            detail["max_size"] = max_size
        super().__init__(
            message="파일 크기가 제한을 초과했습니다.",
            error_code=ContentErrorCode.FILE_SIZE_EXCEEDED,
            detail=detail,
        )


class CacheNotFoundException(NotFoundException):
    """AI 캐시를 찾을 수 없는 경우 (Phase 4)"""

    def __init__(self, content_hash: str | None = None):
        detail = {"content_hash": content_hash} if content_hash else {}
        super().__init__(
            message="AI 캐시를 찾을 수 없습니다.",
            error_code=ContentErrorCode.CACHE_NOT_FOUND,
            detail=detail,
        )
