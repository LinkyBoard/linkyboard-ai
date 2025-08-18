import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from app.user_sync.service import UserSyncService
from app.user_sync.schemas import UserSyncRequest, UserStatusRequest
from app.core.models import User


@pytest.fixture
def mock_session():
    """데이터베이터 세션을 위한 모의(Mock) 객체"""
    return AsyncMock()


@pytest.fixture
def user_sync_service(mocker):
    """UserSyncService 인스턴스와 의존성 모킹"""
    service = UserSyncService()
    
    # UserRepository를 모킹
    mocker.patch.object(service, 'user_repository', new_callable=AsyncMock)
    
    return service


@pytest.fixture
def sample_user():
    """테스트용 사용자 객체"""
    user = MagicMock()
    user.id = 123
    user.ai_preferences = '{"theme": "dark"}'
    user.embedding_model_version = "v1.0"
    user.is_active = True
    user.last_sync_at = datetime.utcnow()
    user.created_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    return user


class TestUserSyncService:
    """UserSyncService 단위 테스트"""
    
    @pytest.mark.asyncio
    async def test_sync_user_create_new(self, user_sync_service, mock_session, sample_user):
        """새 사용자 동기화 테스트"""
        # Given
        request_data = UserSyncRequest(
            user_id=123,
            ai_preferences='{"theme": "dark"}',
            embedding_model_version="v1.0",
            is_active=True
        )
        
        # 기존 사용자 없음
        user_sync_service.user_repository.get_by_id.return_value = None
        # 새 사용자 생성
        user_sync_service.user_repository.create.return_value = sample_user
        
        # When
        result = await user_sync_service.sync_user(mock_session, request_data)
        
        # Then
        assert result.success is True
        assert result.user_id == 123
        assert result.created is True
        assert "생성" in result.message
        
        # 서비스 호출 확인
        user_sync_service.user_repository.get_by_id.assert_called_once_with(mock_session, 123)
        user_sync_service.user_repository.create.assert_called_once()
        user_sync_service.user_repository.update.assert_not_called()
        mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_sync_user_update_existing(self, user_sync_service, mock_session, sample_user):
        """기존 사용자 업데이트 테스트"""
        # Given
        request_data = UserSyncRequest(
            user_id=123,
            ai_preferences='{"theme": "light"}',
            embedding_model_version="v2.0",
            is_active=True
        )
        
        # 기존 사용자 있음
        user_sync_service.user_repository.get_by_id.return_value = sample_user
        # 사용자 업데이트
        user_sync_service.user_repository.update.return_value = sample_user
        
        # When
        result = await user_sync_service.sync_user(mock_session, request_data)
        
        # Then
        assert result.success is True
        assert result.user_id == 123
        assert result.created is False
        assert "업데이트" in result.message
        
        # 서비스 호출 확인
        user_sync_service.user_repository.get_by_id.assert_called_once_with(mock_session, 123)
        user_sync_service.user_repository.update.assert_called_once()
        user_sync_service.user_repository.create.assert_not_called()
        mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_sync_user_database_error(self, user_sync_service, mock_session):
        """데이터베이스 오류 시 예외 발생 테스트"""
        # Given
        request_data = UserSyncRequest(
            user_id=123,
            ai_preferences='{"theme": "dark"}',
            is_active=True
        )
        
        # 데이터베이스 오류 발생
        user_sync_service.user_repository.get_by_id.side_effect = Exception("Database connection failed")
        
        # When & Then
        with pytest.raises(Exception, match="사용자 동기화 중 오류가 발생했습니다"):
            await user_sync_service.sync_user(mock_session, request_data)
        
        # 롤백 호출 확인
        mock_session.rollback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_user_status_success(self, user_sync_service, mock_session, sample_user):
        """사용자 상태 업데이트 성공 테스트"""
        # Given
        request_data = UserStatusRequest(
            user_id=123,
            is_active=False  # 비활성화
        )
        
        # 기존 사용자 있음
        user_sync_service.user_repository.get_by_id.return_value = sample_user
        user_sync_service.user_repository.update.return_value = sample_user
        
        # When
        result = await user_sync_service.update_user_status(mock_session, request_data)
        
        # Then
        assert result.success is True
        assert result.user_id == 123
        assert result.is_active is False
        assert "비활성화" in result.message
        
        # 서비스 호출 확인
        user_sync_service.user_repository.get_by_id.assert_called_once_with(mock_session, 123)
        user_sync_service.user_repository.update.assert_called_once()
        mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_user_status_user_not_found(self, user_sync_service, mock_session):
        """존재하지 않는 사용자 상태 업데이트 테스트"""
        # Given
        request_data = UserStatusRequest(
            user_id=999,  # 존재하지 않는 사용자
            is_active=False
        )
        
        # 사용자 없음
        user_sync_service.user_repository.get_by_id.return_value = None
        
        # When & Then
        with pytest.raises(Exception, match="사용자 상태 변경 중 오류가 발생했습니다"):
            await user_sync_service.update_user_status(mock_session, request_data)
        
        # 롤백 호출 확인
        mock_session.rollback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_sync_status_success(self, user_sync_service, mock_session, sample_user):
        """사용자 동기화 상태 조회 성공 테스트"""
        # Given
        user_id = 123
        user_sync_service.user_repository.get_by_id.return_value = sample_user
        
        # When
        result = await user_sync_service.get_user_sync_status(mock_session, user_id)
        
        # Then
        assert result is not None
        assert result["user_id"] == 123
        assert result["is_active"] is True
        assert result["ai_preferences"] == '{"theme": "dark"}'
        assert result["embedding_model_version"] == "v1.0"
        
        # 서비스 호출 확인
        user_sync_service.user_repository.get_by_id.assert_called_once_with(mock_session, 123)
    
    @pytest.mark.asyncio
    async def test_get_user_sync_status_user_not_found(self, user_sync_service, mock_session):
        """존재하지 않는 사용자 상태 조회 테스트"""
        # Given
        user_id = 999
        user_sync_service.user_repository.get_by_id.return_value = None
        
        # When
        result = await user_sync_service.get_user_sync_status(mock_session, user_id)
        
        # Then
        assert result is None
        
        # 서비스 호출 확인
        user_sync_service.user_repository.get_by_id.assert_called_once_with(mock_session, 999)