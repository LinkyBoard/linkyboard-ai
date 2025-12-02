"""Users 도메인 테스트 - 예외 및 스키마"""

import pytest
from pydantic import ValidationError

from app.domains.users.exceptions import (
    UserAlreadyDeletedException,
    UserNotFoundException,
)
from app.domains.users.schemas import BulkSyncResponse, UserBulkSync, UserSync


class TestUserExceptions:
    """사용자 예외 테스트"""

    def test_user_not_found_exception(self):
        """UserNotFoundException 테스트"""
        exc = UserNotFoundException(user_id=1)
        assert exc.error_code == "USER_NOT_FOUND"
        assert exc.status_code == 404
        assert exc.detail_info == {"user_id": 1}

    def test_user_not_found_exception_without_id(self):
        """UserNotFoundException (ID 없이) 테스트"""
        exc = UserNotFoundException()
        assert exc.error_code == "USER_NOT_FOUND"
        assert exc.status_code == 404
        assert exc.detail_info == {}

    def test_user_already_deleted_exception(self):
        """UserAlreadyDeletedException 테스트"""
        exc = UserAlreadyDeletedException(user_id=1)
        assert exc.error_code == "USER_ALREADY_DELETED"
        assert exc.status_code == 403
        assert exc.detail_info == {"user_id": 1}


class TestUserSchemas:
    """사용자 스키마 테스트"""

    def test_user_sync_schema(self):
        """UserSync 스키마 테스트"""
        user_data = UserSync(id=1)
        assert user_data.id == 1

    def test_user_sync_schema_validation(self):
        """UserSync 스키마 유효성 검사 테스트"""
        # ID는 양수여야 함
        with pytest.raises(ValidationError):
            UserSync(id=0)

        with pytest.raises(ValidationError):
            UserSync(id=-1)

    def test_user_bulk_sync_schema(self):
        """UserBulkSync 스키마 테스트"""
        bulk_data = UserBulkSync(users=[UserSync(id=1), UserSync(id=2)])
        assert len(bulk_data.users) == 2

    def test_user_bulk_sync_validation_max_length(self):
        """UserBulkSync 최대 1000건 제한 테스트"""
        # 1001건은 실패해야 함
        with pytest.raises(ValidationError):
            UserBulkSync(users=[UserSync(id=i) for i in range(1, 1002)])

    def test_user_bulk_sync_validation_min_length(self):
        """UserBulkSync 최소 1건 필요 테스트"""
        with pytest.raises(ValidationError):
            UserBulkSync(users=[])

    def test_bulk_sync_response_schema(self):
        """BulkSyncResponse 스키마 테스트"""
        response = BulkSyncResponse(
            total=100, created=50, updated=30, restored=20
        )
        assert response.total == 100
        assert response.created == 50
        assert response.updated == 30
        assert response.restored == 20
