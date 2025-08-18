import pytest
import json
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.collect.v1.content.service import get_content_service
from app.collect.v1.content.schemas import ItemDeleteResponse

# TestClient 인스턴스 생성
client = TestClient(app)


@pytest.fixture
def mock_content_service():
    """ContentService를 모의(Mock) 객체로 만들고 의존성을 오버라이드합니다."""
    mock_service = AsyncMock()
    
    # 기본 응답 설정
    mock_service.delete_items.return_value = {
        "success": True,
        "deleted_count": 1,
        "failed_items": [],
        "total_requested": 1,
        "results": [
            {
                "item_id": 123,
                "status": "success",
                "title": "Test Item"
            }
        ]
    }
    
    # 의존성 오버라이드 설정
    app.dependency_overrides[get_content_service] = lambda: mock_service
    
    yield mock_service
    
    # 테스트 후 의존성 오버라이드 정리
    app.dependency_overrides.clear()


class TestItemDeleteRouter:
    """Item 삭제 Router 단위 테스트"""
    
    def test_delete_single_item_success(self, mock_content_service):
        """DELETE /api/v1/items 단일 아이템 삭제 성공 테스트"""
        # Given
        request_data = {
            "item_ids": [123],
            "user_id": 456
        }
        
        # When
        response = client.request(
            "DELETE", 
            "/api/v1/items", 
            headers={"Content-Type": "application/json"},
            content=json.dumps(request_data)
        )
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert result["success"] == True
        assert result["deleted_count"] == 1
        assert result["total_requested"] == 1
        assert result["failed_items"] == []
        assert len(result["results"]) == 1
        assert "성공적으로 삭제되었습니다" in result["message"]
        
        # 서비스 호출 확인
        mock_content_service.delete_items.assert_called_once()
        call_args = mock_content_service.delete_items.call_args
        args, kwargs = call_args
        request_obj = args[1]  # session이 첫 번째, request_data가 두 번째
        
        assert request_obj.item_ids == [123]
        assert request_obj.user_id == 456
    
    def test_delete_multiple_items_success(self, mock_content_service):
        """DELETE /api/v1/items 다중 아이템 삭제 성공 테스트"""
        # Given
        request_data = {
            "item_ids": [123, 456, 789],
            "user_id": 1001
        }
        
        mock_content_service.delete_items.return_value = {
            "success": True,
            "deleted_count": 3,
            "failed_items": [],
            "total_requested": 3,
            "results": [
                {"item_id": 123, "status": "success", "title": "Item 1"},
                {"item_id": 456, "status": "success", "title": "Item 2"},
                {"item_id": 789, "status": "success", "title": "Item 3"}
            ]
        }
        
        # When
        response = client.request(
            "DELETE", 
            "/api/v1/items", 
            headers={"Content-Type": "application/json"},
            content=json.dumps(request_data)
        )
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert result["success"] == True
        assert result["deleted_count"] == 3
        assert result["total_requested"] == 3
        assert result["failed_items"] == []
        assert len(result["results"]) == 3
        
    def test_delete_items_partial_failure(self, mock_content_service):
        """DELETE /api/v1/items 부분 실패 테스트"""
        # Given
        request_data = {
            "item_ids": [123, 456, 789],
            "user_id": 1001
        }
        
        mock_content_service.delete_items.return_value = {
            "success": False,
            "deleted_count": 2,
            "failed_items": [789],
            "total_requested": 3,
            "results": [
                {"item_id": 123, "status": "success", "title": "Item 1"},
                {"item_id": 456, "status": "success", "title": "Item 2"},
                {"item_id": 789, "status": "failed", "reason": "Item not found or access denied"}
            ]
        }
        
        # When
        response = client.request(
            "DELETE", 
            "/api/v1/items", 
            headers={"Content-Type": "application/json"},
            content=json.dumps(request_data)
        )
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert result["success"] == False
        assert result["deleted_count"] == 2
        assert result["total_requested"] == 3
        assert result["failed_items"] == [789]
        assert len(result["results"]) == 3
        assert "2/3개의 아이템이 삭제되었습니다" in result["message"]
        
    def test_delete_items_validation_error(self, mock_content_service):
        """DELETE /api/v1/items 유효성 검증 실패 테스트"""
        # Given - 빈 item_ids 배열
        request_data = {
            "item_ids": [],
            "user_id": 1001
        }
        
        # When
        response = client.request(
            "DELETE", 
            "/api/v1/items", 
            headers={"Content-Type": "application/json"},
            content=json.dumps(request_data)
        )
        
        # Then
        assert response.status_code == 422  # Validation Error
        
        # 서비스가 호출되지 않았는지 확인
        mock_content_service.delete_items.assert_not_called()
        
    def test_delete_items_missing_fields(self, mock_content_service):
        """DELETE /api/v1/items 필수 필드 누락 테스트"""
        # Given - user_id 누락
        request_data = {
            "item_ids": [123, 456]
        }
        
        # When
        response = client.request(
            "DELETE", 
            "/api/v1/items", 
            headers={"Content-Type": "application/json"},
            content=json.dumps(request_data)
        )
        
        # Then
        assert response.status_code == 422  # Validation Error
        
        # 서비스가 호출되지 않았는지 확인
        mock_content_service.delete_items.assert_not_called()
        
    def test_delete_items_service_error(self, mock_content_service):
        """DELETE /api/v1/items 서비스 오류 테스트"""
        # Given
        request_data = {
            "item_ids": [123],
            "user_id": 456
        }
        
        mock_content_service.delete_items.side_effect = Exception("Database connection failed")
        
        # When
        response = client.request(
            "DELETE", 
            "/api/v1/items", 
            headers={"Content-Type": "application/json"},
            content=json.dumps(request_data)
        )
        
        # Then
        assert response.status_code == 500
        result = response.json()
        assert "Database connection failed" in result["detail"]
        
    def test_delete_items_detailed_results(self, mock_content_service):
        """DELETE /api/v1/items 상세 결과 포함 테스트"""
        # Given
        request_data = {
            "item_ids": [123, 456],
            "user_id": 789
        }
        
        mock_content_service.delete_items.return_value = {
            "success": True,
            "deleted_count": 2,
            "failed_items": [],
            "total_requested": 2,
            "results": [
                {"item_id": 123, "status": "success", "title": "Test Item 1"},
                {"item_id": 456, "status": "success", "title": "Test Item 2"}
            ]
        }
        
        # When
        response = client.request(
            "DELETE", 
            "/api/v1/items", 
            headers={"Content-Type": "application/json"},
            content=json.dumps(request_data)
        )
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert result["success"] == True
        assert "성공적으로 삭제되었습니다" in result["message"]
        assert len(result["results"]) == 2
        
        # 각 결과에 필요한 정보가 포함되어 있는지 확인
        for item_result in result["results"]:
            assert "item_id" in item_result
            assert "status" in item_result
            assert item_result["status"] == "success"