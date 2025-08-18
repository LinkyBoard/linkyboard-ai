import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app
from app.board_ai.router import router
from app.board_ai.service import board_ai_service

# TestClient 인스턴스 생성
client = TestClient(app)


@pytest.fixture
def mock_board_ai_service(mocker):
    """BoardAIService를 모의(Mock) 객체로 만들고 의존성을 오버라이드합니다."""
    mock_service = AsyncMock()
    mocker.patch('app.board_ai.router.board_ai_service', mock_service)
    return mock_service


@pytest.fixture
def sample_board_id():
    """테스트용 보드 ID"""
    return str(uuid4())


@pytest.fixture
def sample_user_id():
    """테스트용 사용자 ID"""
    return 12345


class TestBoardAIRouter:
    """BoardAI Router 단위 테스트 - 선택된 아이템 기반"""
    
    def test_get_available_models_success(self, mock_board_ai_service):
        """GET /board-ai/models/available 엔드포인트 성공 테스트"""
        # Given
        expected_response = {
            "models": [
                {
                    "alias": "GPT-4o Mini",
                    "model_name": "gpt-4o-mini",
                    "provider": "openai",
                    "description": "Fast and cost-effective model",
                    "input_cost_per_1k": 1000.0,
                    "output_cost_per_1k": 4000.0,
                    "is_default": True
                }
            ],
            "total_count": 1,
            "default_model": "GPT-4o Mini"
        }
        
        mock_board_ai_service.get_available_models.return_value = expected_response
        
        # When
        response = client.get("/board-ai/models/available")
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert result["total_count"] == 1
        assert result["default_model"] == "GPT-4o Mini"
        assert len(result["models"]) == 1
        
        # 서비스 호출 확인
        mock_board_ai_service.get_available_models.assert_called_once()
    
    def test_estimate_cost_success(self, mock_board_ai_service, sample_board_id, sample_user_id):
        """POST /board-ai/models/estimate-cost 엔드포인트 성공 테스트"""
        # Given
        request_data = {
            "selected_items": [1, 2, 3],
            "task_description": "이 아이템들을 요약해주세요",
            "board_id": sample_board_id,
            "user_id": sample_user_id,
            "estimated_output_tokens": 1500
        }
        
        expected_response = {
            "estimates": [
                {
                    "model_alias": "GPT-4o Mini",
                    "model_name": "gpt-4o-mini",
                    "provider": "openai",
                    "estimated_input_tokens": 2000,
                    "estimated_output_tokens": 1500,
                    "estimated_wtu_cost": 8000,
                    "is_recommended": True
                }
            ],
            "total_selected_items": 3,
            "total_content_length": 5000
        }
        
        mock_board_ai_service.estimate_task_cost.return_value = expected_response
        
        # When
        response = client.post("/board-ai/models/estimate-cost", json=request_data)
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert result["total_selected_items"] == 3
        assert len(result["estimates"]) == 1
        assert result["estimates"][0]["is_recommended"] == True
        
        # 서비스 호출 확인
        mock_board_ai_service.estimate_task_cost.assert_called_once()
    
    def test_ask_with_items_success(self, mock_board_ai_service, sample_board_id, sample_user_id):
        """POST /board-ai/ask-with-items 엔드포인트 성공 테스트"""
        # Given
        request_data = {
            "query": "이 아이템들의 공통점은 무엇인가요?",
            "instruction": "주요 공통점을 분석하고 간단히 설명해주세요",
            "selected_items": [
                {
                    "item_id": 1,
                    "include_summary": True,
                    "include_content": False
                },
                {
                    "item_id": 2,
                    "include_summary": True,
                    "include_content": True
                }
            ],
            "board_id": sample_board_id,
            "user_id": sample_user_id,
            "model_alias": "GPT-4o Mini",
            "max_output_tokens": 1500
        }
        
        expected_response = {
            "answer_md": "# 공통점 분석\n\n두 아이템의 주요 공통점은...",
            "used_items": [
                {
                    "item_id": 1,
                    "title": "테스트 아이템 1",
                    "url": "https://example.com/1",
                    "included_summary": True,
                    "included_content": False
                }
            ],
            "usage": {
                "input_tokens": 2000,
                "output_tokens": 800,
                "total_tokens": 2800
            },
            "model_info": {
                "alias": "GPT-4o Mini",
                "model_name": "gpt-4o-mini",
                "provider": "openai"
            }
        }
        
        mock_board_ai_service.ask_with_selected_items.return_value = expected_response
        
        # When
        response = client.post("/board-ai/ask-with-items", json=request_data)
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert "공통점 분석" in result["answer_md"]
        assert result["model_info"]["alias"] == "GPT-4o Mini"
        assert len(result["used_items"]) == 1
        
        # 서비스 호출 확인
        mock_board_ai_service.ask_with_selected_items.assert_called_once()
    
    def test_ask_with_items_validation_error(self, mock_board_ai_service):
        """POST /board-ai/ask-with-items 유효성 검증 실패 테스트"""
        # Given - 필수 필드 누락
        request_data = {
            "query": "테스트 질문",
            "instruction": "테스트 지시",
            # selected_items 누락
            # board_id 누락
            # user_id 누락
            "model_alias": "GPT-4o Mini"
        }
        
        # When
        response = client.post("/board-ai/ask-with-items", json=request_data)
        
        # Then
        assert response.status_code == 422  # Validation Error
        
        # 서비스가 호출되지 않았는지 확인
        mock_board_ai_service.ask_with_selected_items.assert_not_called()
    
    def test_ask_with_items_model_not_found(self, mock_board_ai_service, sample_board_id, sample_user_id):
        """POST /board-ai/ask-with-items 모델 없음 테스트"""
        # Given
        request_data = {
            "query": "테스트 질문",
            "instruction": "테스트 지시",
            "selected_items": [{"item_id": 1}],
            "board_id": sample_board_id,
            "user_id": sample_user_id,
            "model_alias": "NonExistent Model"
        }
        
        # 서비스에서 ValueError 발생 설정
        mock_board_ai_service.ask_with_selected_items.side_effect = ValueError("Model 'NonExistent Model' not found")
        
        # When
        response = client.post("/board-ai/ask-with-items", json=request_data)
        
        # Then
        assert response.status_code == 400  # Bad Request
        result = response.json()
        assert "Model 'NonExistent Model' not found" in result["detail"]
    
    def test_draft_with_items_success(self, mock_board_ai_service, sample_board_id, sample_user_id):
        """POST /board-ai/draft-with-items 엔드포인트 성공 테스트"""
        # Given
        request_data = {
            "content_type": "blog_post",
            "requirements": "친근하고 이해하기 쉬운 톤으로 작성해주세요",
            "selected_items": [
                {
                    "item_id": 1,
                    "include_summary": True,
                    "include_content": True
                }
            ],
            "board_id": sample_board_id,
            "user_id": sample_user_id,
            "model_alias": "GPT-4o Mini",
            "max_output_tokens": 2000
        }
        
        expected_response = {
            "draft_md": "# 블로그 포스트 초안\n\n안녕하세요! 오늘은...",
            "used_items": [
                {
                    "item_id": 1,
                    "title": "테스트 아이템",
                    "url": "https://example.com/1",
                    "included_summary": True,
                    "included_content": True
                }
            ],
            "usage": {
                "input_tokens": 3000,
                "output_tokens": 1200,
                "total_tokens": 4200
            },
            "model_info": {
                "alias": "GPT-4o Mini",
                "model_name": "gpt-4o-mini",
                "provider": "openai"
            }
        }
        
        mock_board_ai_service.draft_with_selected_items.return_value = expected_response
        
        # When
        response = client.post("/board-ai/draft-with-items", json=request_data)
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert "블로그 포스트 초안" in result["draft_md"]
        assert result["model_info"]["alias"] == "GPT-4o Mini"
        assert len(result["used_items"]) == 1
        
        # 서비스 호출 확인
        mock_board_ai_service.draft_with_selected_items.assert_called_once()
    
    def test_draft_with_items_server_error(self, mock_board_ai_service, sample_board_id, sample_user_id):
        """POST /board-ai/draft-with-items 서버 오류 테스트"""
        # Given
        request_data = {
            "content_type": "report",
            "requirements": "전문적인 분석 리포트로 작성해주세요",
            "selected_items": [{"item_id": 1}],
            "board_id": sample_board_id,
            "user_id": sample_user_id,
            "model_alias": "GPT-4o Mini"
        }
        
        # 서비스에서 예외 발생 설정
        mock_board_ai_service.draft_with_selected_items.side_effect = Exception("AI service unavailable")
        
        # When
        response = client.post("/board-ai/draft-with-items", json=request_data)
        
        # Then
        assert response.status_code == 500  # Internal Server Error
        result = response.json()
        assert "선택된 아이템 기반 초안 작성 중 오류가 발생했습니다" in result["detail"]