"""Users 도메인 예외 정의"""

from enum import Enum

from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)


class UserErrorCode(str, Enum):
    """사용자 도메인 에러 코드"""

    USER_NOT_FOUND = "USER_NOT_FOUND"
    USER_ALREADY_EXISTS = "USER_ALREADY_EXISTS"
    USER_INACTIVE = "USER_INACTIVE"
    INVALID_PASSWORD = "INVALID_PASSWORD"
    USERNAME_ALREADY_EXISTS = "USERNAME_ALREADY_EXISTS"


class UserNotFoundException(NotFoundException):
    """사용자를 찾을 수 없는 경우"""

    def __init__(self, user_id: int | str | None = None):
        detail = {"user_id": user_id} if user_id else {}
        super().__init__(
            message="사용자를 찾을 수 없습니다.",
            error_code=UserErrorCode.USER_NOT_FOUND,
            detail=detail,
        )


class UserAlreadyExistsException(ConflictException):
    """사용자가 이미 존재하는 경우"""

    def __init__(self, username: str | None = None):
        detail = {"username": username} if username else {}
        super().__init__(
            message="이미 존재하는 사용자입니다.",
            error_code=UserErrorCode.USER_ALREADY_EXISTS,
            detail=detail,
        )


class UsernameAlreadyExistsException(ConflictException):
    """사용자명이 이미 존재하는 경우"""

    def __init__(self, username: str):
        super().__init__(
            message="이미 사용 중인 사용자명입니다.",
            error_code=UserErrorCode.USERNAME_ALREADY_EXISTS,
            detail={"username": username},
        )


class UserInactiveException(ForbiddenException):
    """비활성화된 사용자인 경우"""

    def __init__(self):
        super().__init__(
            message="비활성화된 사용자입니다.",
            error_code=UserErrorCode.USER_INACTIVE,
        )


class InvalidPasswordException(UnauthorizedException):
    """비밀번호가 올바르지 않은 경우"""

    def __init__(self):
        super().__init__(
            message="비밀번호가 올바르지 않습니다.",
            error_code=UserErrorCode.INVALID_PASSWORD,
        )
