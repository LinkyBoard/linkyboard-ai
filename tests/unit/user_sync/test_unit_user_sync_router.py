import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime

from app.main import app
from app.user_sync.router import router
from app.user_sync.service import user_sync_service

# TestClient 인스턴스 생성
client = TestClient(app)


@pytest.fixture
def mock_user_sync_service(mocker):
    """UserSyncService를 모의(Mock) 객체로 만들고 의존성을 오버라이드합니다."""
    mock_service = AsyncMock()
    mocker.patch('app.user_sync.router.get_user_sync_service', return_value=mock_service)
    return mock_service


class TestUserSyncRouter:
    """UserSync Router 단위 테스트"""
    
    def test_sync_user_success(self, mock_user_sync_service):
        """POST /user-sync/sync 엔드포인트 성공 테스트"""
        # Given
        request_data = {
            "user_id": 123,
            "is_active": True
        }
        
        expected_response = {
            "success": True,
            "message": "사용자 123가 성공적으로 생성되었습니다.",
            "user_id": 123,
            "created": True,
            "last_sync_at": "2025-08-18T15:52:00.000Z"
        }
        
        mock_user_sync_service.sync_user.return_value = type('MockResponse', (), expected_response)()
        
        # When
        response = client.post("/user-sync/sync", json=request_data)
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["user_id"] == 123
        assert result["created"] is True
        assert "생성" in result["message"]
        
        # 서비스 호출 확인
        mock_user_sync_service.sync_user.assert_called_once()
    
    def test_sync_user_validation_error(self, mock_user_sync_service):
        """POST /user-sync/sync 유효성 검증 실패 테스트"""
        # Given - 필수 필드 누락
        request_data = {
            "is_active": True
            # user_id 누락
        }
        
        # When
        response = client.post("/user-sync/sync", json=request_data)
        
        # Then
        assert response.status_code == 422  # Validation Error
        
        # 서비스가 호출되지 않았는지 확인
        mock_user_sync_service.sync_user.assert_not_called()
    
    def test_sync_user_server_error(self, mock_user_sync_service):
        """POST /user-sync/sync 서버 오류 테스트"""
        # Given
        request_data = {
            "user_id": 123,
            "is_active": True
        }
        
        # 서비스에서 예외 발생 설정
        mock_user_sync_service.sync_user.side_effect = Exception("Database connection failed")
        
        # When
        response = client.post("/user-sync/sync", json=request_data)
        
        # Then
        assert response.status_code == 500  # Internal Server Error
        result = response.json()
        assert "사용자 동기화 중 오류가 발생했습니다" in result["detail"]
    
    def test_update_user_status_success(self, mock_user_sync_service):
        """PUT /user-sync/status 엔드포인트 성공 테스트"""
        # Given
        request_data = {
            "user_id": 123,
            "is_active": False
        }
        
        expected_response = {
            "success": True,
            "message": "사용자 123가 성공적으로 비활성화되었습니다.",
            "user_id": 123,
            "is_active": False
        }
        
        mock_user_sync_service.update_user_status.return_value = type('MockResponse', (), expected_response)()
        
        # When
        response = client.put("/user-sync/status", json=request_data)
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["user_id"] == 123
        assert result["is_active"] is False
        assert "비활성화" in result["message"]
        
        # 서비스 호출 확인
        mock_user_sync_service.update_user_status.assert_called_once()
    
    def test_update_user_status_validation_error(self, mock_user_sync_service):
        """PUT /user-sync/status 유효성 검증 실패 테스트"""
        # Given - 잘못된 데이터 타입
        request_data = {
            "user_id": "not-a-number",  # 숫자여야 함
            "is_active": "not-a-boolean"  # 불린값이어야 함
        }
        
        # When
        response = client.put("/user-sync/status", json=request_data)
        
        # Then
        assert response.status_code == 422  # Validation Error
        
        # 서비스가 호출되지 않았는지 확인
        mock_user_sync_service.update_user_status.assert_not_called()
    
    def test_update_user_status_user_not_found(self, mock_user_sync_service):
        """PUT /user-sync/status 사용자 없음 테스트"""
        # Given
        request_data = {
            "user_id": 999,  # 존재하지 않는 사용자
            "is_active": False
        }
        
        # 서비스에서 ValueError 발생 설정
        mock_user_sync_service.update_user_status.side_effect = ValueError("사용자 999를 찾을 수 없습니다.")
        
        # When
        response = client.put("/user-sync/status", json=request_data)
        
        # Then
        assert response.status_code == 400  # Bad Request
        result = response.json()
        assert "사용자 999를 찾을 수 없습니다" in result["detail"]
    
    def test_get_user_sync_status_success(self, mock_user_sync_service):
        """GET /user-sync/status/{user_id} 엔드포인트 성공 테스트"""
        # Given
        user_id = 123
        
        expected_response = {
            "user_id": 123,
            "is_active": True,
            "ai_preferences": '{"theme": "dark"}',
            "embedding_model_version": "v1.0",
            "last_sync_at": "2025-08-18T15:52:00.000Z",
            "created_at": "2025-08-18T15:52:00.000Z",
            "updated_at": "2025-08-18T15:52:00.000Z"
        }
        
        mock_user_sync_service.get_user_sync_status.return_value = expected_response
        
        # When
        response = client.get(f"/user-sync/status/{user_id}")
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert result["user_id"] == 123
        assert result["is_active"] is True
        assert result["ai_preferences"] == '{"theme": "dark"}'
        assert result["embedding_model_version"] == "v1.0"
        
        # 서비스 호출 확인
        mock_user_sync_service.get_user_sync_status.assert_called_once()
    
    def test_get_user_sync_status_user_not_found(self, mock_user_sync_service):
        """GET /user-sync/status/{user_id} 사용자 없음 테스트"""
        # Given
        user_id = 999
        
        # 서비스에서 None 반환 (사용자 없음)
        mock_user_sync_service.get_user_sync_status.return_value = None
        
        # When
        response = client.get(f"/user-sync/status/{user_id}")
        
        # Then
        assert response.status_code == 404  # Not Found
        result = response.json()
        assert "사용자를 찾을 수 없습니다" in result["detail"]
    
    def test_get_user_sync_status_server_error(self, mock_user_sync_service):
        """GET /user-sync/status/{user_id} 서버 오류 테스트"""
        # Given
        user_id = 123
        
        # 서비스에서 예외 발생 설정
        mock_user_sync_service.get_user_sync_status.side_effect = Exception("Database error")
        
        # When
        response = client.get(f"/user-sync/status/{user_id}")
        
        # Then
        assert response.status_code == 500  # Internal Server Error
        result = response.json()
        assert "사용자 상태 조회 중 오류가 발생했습니다" in result["detail"]