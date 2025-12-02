"""Users 도메인 예외 정의"""

from enum import Enum

from app.core.exceptions import ForbiddenException, NotFoundException


class UserErrorCode(str, Enum):
    """사용자 도메인 에러 코드"""

    USER_NOT_FOUND = "USER_NOT_FOUND"
    USER_ALREADY_DELETED = "USER_ALREADY_DELETED"


class UserNotFoundException(NotFoundException):
    """사용자를 찾을 수 없는 경우"""

    def __init__(self, user_id: int | None = None):
        detail = {"user_id": user_id} if user_id else {}
        super().__init__(
            message="사용자를 찾을 수 없습니다.",
            error_code=UserErrorCode.USER_NOT_FOUND,
            detail=detail,
        )


class UserAlreadyDeletedException(ForbiddenException):
    """이미 삭제된 사용자인 경우"""

    def __init__(self, user_id: int | None = None):
        detail = {"user_id": user_id} if user_id else {}
        super().__init__(
            message="이미 삭제된 사용자입니다.",
            error_code=UserErrorCode.USER_ALREADY_DELETED,
            detail=detail,
        )
