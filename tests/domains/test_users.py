"""Users 도메인 테스트"""

import pytest


class TestUserExceptions:
    """사용자 예외 테스트"""

    def test_user_not_found_exception(self):
        """UserNotFoundException 테스트"""
        from app.domains.users.exceptions import UserNotFoundException

        exc = UserNotFoundException(user_id=1)
        assert exc.error_code == "USER_NOT_FOUND"
        assert exc.status_code == 404
        assert exc.detail_info == {"user_id": 1}

    def test_username_already_exists_exception(self):
        """UsernameAlreadyExistsException 테스트"""
        from app.domains.users.exceptions import UsernameAlreadyExistsException

        exc = UsernameAlreadyExistsException(username="testuser")
        assert exc.error_code == "USERNAME_ALREADY_EXISTS"
        assert exc.status_code == 409
        assert exc.detail_info == {"username": "testuser"}


class TestUserSchemas:
    """사용자 스키마 테스트"""

    def test_user_create_schema(self):
        """UserCreate 스키마 테스트"""
        from app.domains.users.schemas import UserCreate

        user_data = UserCreate(
            username="testuser",
            full_name="Test User",
            password="password123",
        )
        assert user_data.username == "testuser"
        assert user_data.full_name == "Test User"

    def test_user_create_schema_validation(self):
        """UserCreate 스키마 유효성 검사 테스트"""
        from pydantic import ValidationError

        from app.domains.users.schemas import UserCreate

        # 짧은 비밀번호
        with pytest.raises(ValidationError):
            UserCreate(
                username="testuser",
                password="short",
            )

        # 짧은 사용자명
        with pytest.raises(ValidationError):
            UserCreate(
                username="ab",
                password="password123",
            )
