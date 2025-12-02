"""User Service 단위 테스트"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domains.users.exceptions import UserNotFoundException
from app.domains.users.models import User
from app.domains.users.schemas import UserSync
from app.domains.users.service import UserService


@pytest.fixture
def mock_session():
    """Mock AsyncSession"""
    return MagicMock()


@pytest.fixture
def user_service(mock_session):
    """UserService 인스턴스"""
    return UserService(mock_session)


class TestUserServiceGet:
    """UserService 조회 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_user_success(self, user_service):
        """사용자 조회 성공 테스트"""
        # Given
        mock_user = User(id=1, last_sync_at=datetime.now())
        user_service.repository.get_by_id = AsyncMock(return_value=mock_user)

        # When
        result = await user_service.get_user(1)

        # Then
        assert result == mock_user
        user_service.repository.get_by_id.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, user_service):
        """사용자 조회 실패 테스트 (사용자 없음)"""
        # Given
        user_service.repository.get_by_id = AsyncMock(return_value=None)

        # When & Then
        with pytest.raises(UserNotFoundException):
            await user_service.get_user(999)

    @pytest.mark.asyncio
    async def test_get_users_list(self, user_service):
        """사용자 목록 조회 테스트"""
        # Given
        mock_users = [
            User(id=1, last_sync_at=datetime.now()),
            User(id=2, last_sync_at=datetime.now()),
        ]
        user_service.repository.get_list = AsyncMock(return_value=mock_users)
        user_service.repository.count = AsyncMock(return_value=2)

        # When
        users, total = await user_service.get_users(page=1, size=20)

        # Then
        assert len(users) == 2
        assert total == 2
        user_service.repository.get_list.assert_called_once()
        user_service.repository.count.assert_called_once()


class TestUserServiceUpsert:
    """UserService Upsert 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_upsert_user_create_new(self, user_service):
        """새 사용자 생성 테스트"""
        # Given
        user_data = UserSync(id=1)
        user_service.repository.get_by_id = AsyncMock(return_value=None)
        created_user = User(id=1, last_sync_at=datetime.now())
        user_service.repository.create = AsyncMock(return_value=created_user)

        # When
        with patch("app.domains.users.service.logger") as mock_logger:
            result = await user_service.upsert_user(user_data)

            # Then
            assert result.id == 1
            user_service.repository.create.assert_called_once()
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_user_update_existing(self, user_service):
        """기존 사용자 업데이트 테스트"""
        # Given
        user_data = UserSync(id=1)
        existing_user = User(
            id=1, deleted_at=None, last_sync_at=datetime.now()
        )
        user_service.repository.get_by_id = AsyncMock(
            return_value=existing_user
        )
        user_service.repository.update = AsyncMock(return_value=existing_user)

        # When
        with patch("app.domains.users.service.logger") as mock_logger:
            result = await user_service.upsert_user(user_data)

            # Then
            assert result.id == 1
            user_service.repository.update.assert_called_once()
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_user_restore_deleted(self, user_service):
        """삭제된 사용자 복구 테스트"""
        # Given
        user_data = UserSync(id=1)
        deleted_user = User(
            id=1, deleted_at=datetime.now(), last_sync_at=datetime.now()
        )
        user_service.repository.get_by_id = AsyncMock(
            return_value=deleted_user
        )
        user_service.repository.update = AsyncMock(return_value=deleted_user)

        # When
        with patch("app.domains.users.service.logger") as mock_logger:
            result = await user_service.upsert_user(user_data)

            # Then
            assert result.id == 1
            assert result.deleted_at is None  # 복구됨
            user_service.repository.update.assert_called_once()
            mock_logger.info.assert_called_once()


class TestUserServiceBulkUpsert:
    """UserService 벌크 Upsert 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_bulk_upsert_mixed_operations(self, user_service):
        """벌크 동기화 - 혼합 작업 테스트"""
        # Given
        users = [
            UserSync(id=1),  # 새 사용자
            UserSync(id=2),  # 기존 사용자
            UserSync(id=3),  # 삭제된 사용자 (복구)
        ]

        async def mock_get_by_id(user_id, include_deleted=False):
            if user_id == 1:
                return None  # 새 사용자
            elif user_id == 2:
                return User(id=2, deleted_at=None, last_sync_at=datetime.now())
            else:  # user_id == 3
                return User(
                    id=3,
                    deleted_at=datetime.now(),
                    last_sync_at=datetime.now(),
                )

        user_service.repository.get_by_id = AsyncMock(
            side_effect=mock_get_by_id
        )
        user_service.repository.create = AsyncMock()
        user_service.repository.update = AsyncMock()

        # When
        with patch("app.domains.users.service.logger"):
            result = await user_service.bulk_upsert_users(users)

            # Then
            assert result.total == 3
            assert result.created == 1
            assert result.updated == 1
            assert result.restored == 1


class TestUserServiceDelete:
    """UserService 삭제 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_delete_user_success(self, user_service):
        """사용자 삭제 성공 테스트"""
        # Given
        mock_user = User(id=1, last_sync_at=datetime.now())
        user_service.repository.get_by_id = AsyncMock(return_value=mock_user)
        user_service.repository.soft_delete = AsyncMock()

        # When
        with patch("app.domains.users.service.logger") as mock_logger:
            await user_service.delete_user(1)

            # Then
            user_service.repository.soft_delete.assert_called_once_with(
                mock_user
            )
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, user_service):
        """존재하지 않는 사용자 삭제 실패 테스트"""
        # Given
        user_service.repository.get_by_id = AsyncMock(return_value=None)

        # When & Then
        with pytest.raises(UserNotFoundException):
            await user_service.delete_user(999)
