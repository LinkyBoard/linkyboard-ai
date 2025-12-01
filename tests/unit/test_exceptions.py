"""예외 단위 테스트"""

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ErrorCode,
    ForbiddenException,
    InternalServerException,
    NotFoundException,
    UnauthorizedException,
)
from app.domains.users.exceptions import (
    UserErrorCode,
    UsernameAlreadyExistsException,
    UserNotFoundException,
)


class TestGlobalExceptions:
    """전역 예외 테스트"""

    def test_not_found_exception(self):
        """NotFoundException 기본값"""
        exc = NotFoundException()

        assert exc.status_code == 404
        assert exc.error_code == ErrorCode.NOT_FOUND
        assert exc.message == "리소스를 찾을 수 없습니다."

    def test_not_found_exception_custom(self):
        """NotFoundException 커스텀 메시지"""
        exc = NotFoundException(
            message="게시글을 찾을 수 없습니다.",
            detail={"post_id": 123},
        )

        assert exc.message == "게시글을 찾을 수 없습니다."
        assert exc.detail_info == {"post_id": 123}

    def test_bad_request_exception(self):
        """BadRequestException"""
        exc = BadRequestException(message="잘못된 입력입니다.")

        assert exc.status_code == 400
        assert exc.error_code == ErrorCode.BAD_REQUEST

    def test_unauthorized_exception(self):
        """UnauthorizedException"""
        exc = UnauthorizedException()

        assert exc.status_code == 401
        assert exc.error_code == ErrorCode.UNAUTHORIZED

    def test_forbidden_exception(self):
        """ForbiddenException"""
        exc = ForbiddenException()

        assert exc.status_code == 403
        assert exc.error_code == ErrorCode.FORBIDDEN

    def test_conflict_exception(self):
        """ConflictException"""
        exc = ConflictException()

        assert exc.status_code == 409
        assert exc.error_code == ErrorCode.CONFLICT

    def test_internal_server_exception(self):
        """InternalServerException"""
        exc = InternalServerException()

        assert exc.status_code == 500
        assert exc.error_code == ErrorCode.INTERNAL_ERROR


class TestDomainExceptions:
    """도메인 예외 테스트"""

    def test_user_not_found_exception(self):
        """UserNotFoundException"""
        exc = UserNotFoundException(user_id=123)

        assert exc.status_code == 404
        assert exc.error_code == UserErrorCode.USER_NOT_FOUND
        assert exc.message == "사용자를 찾을 수 없습니다."
        assert exc.detail_info == {"user_id": 123}

    def test_username_already_exists_exception(self):
        """UsernameAlreadyExistsException"""
        exc = UsernameAlreadyExistsException(username="testuser")

        assert exc.status_code == 409
        assert exc.error_code == UserErrorCode.USERNAME_ALREADY_EXISTS
        assert exc.detail_info == {"username": "testuser"}
