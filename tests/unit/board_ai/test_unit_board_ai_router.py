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
    """BoardAI Router 단위 테스트"""
    
    def test_ask_success(self, mock_board_ai_service, sample_board_id, sample_user_id):
        """POST /board-ai/ask 엔드포인트 성공 테스트"""
        # Given
        request_data = {
            "query": "테스트 질문입니다",
            "board_id": sample_board_id,
            "user_id": sample_user_id,
            "k": 4,
            "max_out_tokens": 800,
            "model": "GPT-3.5"
        }
        
        expected_response = {
            "answer_md": "테스트 답변입니다",
            "claims": [],
            "usage": {
                "in": 50,
                "cached_in": 0,
                "out": 100,
                "embed": 0,
                "wtu": 450
            },
            "routing": {
                "selected_model": "GPT-3.5",
                "stoploss_triggered": False
            }
        }
        
        mock_board_ai_service.ask_with_model_selection.return_value = expected_response
        
        # When
        response = client.post("/board-ai/ask", json=request_data)
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert result["answer_md"] == "테스트 답변입니다"
        assert result["usage"]["wtu"] == 450
        assert result["routing"]["selected_model"] == "GPT-3.5"
        
        # 서비스 호출 확인
        mock_board_ai_service.ask_with_model_selection.assert_called_once()
    
    def test_ask_validation_error(self, mock_board_ai_service):
        """POST /board-ai/ask 유효성 검증 실패 테스트"""
        # Given - 필수 필드 누락
        request_data = {
            "query": "",  # 빈 쿼리
            "board_id": "invalid-uuid",  # 잘못된 UUID
            "user_id": "not-a-number"  # 잘못된 사용자 ID
        }
        
        # When
        response = client.post("/board-ai/ask", json=request_data)
        
        # Then
        assert response.status_code == 422  # Validation Error
        
        # 서비스가 호출되지 않았는지 확인
        mock_board_ai_service.ask_with_model_selection.assert_not_called()
    
    def test_ask_with_items_success(self, mock_board_ai_service, sample_board_id, sample_user_id):
        """POST /board-ai/ask-with-items 엔드포인트 성공 테스트"""
        # Given
        request_data = {
            "query": "선택된 아이템에 대한 질문",
            "instruction": "아이템 내용을 요약해주세요",
            "selected_items": [
                {
                    "item_id": 123,
                    "include_summary": True,
                    "include_content": True
                }
            ],
            "board_id": sample_board_id,
            "user_id": sample_user_id,
            "model": "GPT-3.5"
        }
        
        expected_response = {
            "answer_md": "선택된 아이템 기반 답변",
            "used_items": [
                {
                    "item_id": 123,
                    "title": "테스트 아이템",
                    "url": "https://example.com",
                    "item_type": "webpage",
                    "included_summary": True,
                    "included_content": True
                }
            ],
            "usage": {
                "in": 200,
                "cached_in": 0,
                "out": 150,
                "embed": 0,
                "total_wtu": 800
            },
            "routing": {
                "selected_model": "GPT-3.5",
                "stoploss_triggered": False
            }
        }
        
        mock_board_ai_service.ask_with_selected_items.return_value = expected_response
        
        # When
        response = client.post("/board-ai/ask-with-items", json=request_data)
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert result["answer_md"] == "선택된 아이템 기반 답변"
        assert len(result["used_items"]) == 1
        assert result["used_items"][0]["item_id"] == 123
        
        # 서비스 호출 확인
        mock_board_ai_service.ask_with_selected_items.assert_called_once()
    
    def test_ask_with_items_empty_items(self, mock_board_ai_service, sample_board_id, sample_user_id):
        """POST /board-ai/ask-with-items 아이템 없음 테스트"""
        # Given
        request_data = {
            "query": "아이템 없이 질문",
            "instruction": "처리할 아이템 없음",
            "selected_items": [{"item_id": 999, "include_summary": True}],  # 존재하지 않는 아이템
            "board_id": sample_board_id,
            "user_id": sample_user_id
        }
        
        # 서비스에서 유효하지 않은 아이템 예외 발생 설정
        mock_board_ai_service.ask_with_selected_items.side_effect = ValueError("선택된 아이템 중 사용할 수 있는 것이 없습니다.")
        
        # When
        response = client.post("/board-ai/ask-with-items", json=request_data)
        
        # Then
        assert response.status_code == 400  # Bad Request
    
    def test_draft_success(self, mock_board_ai_service, sample_board_id, sample_user_id):
        """POST /board-ai/draft 엔드포인트 성공 테스트"""
        # Given
        request_data = {
            "outline": ["서론", "본론", "결론"],
            "board_id": sample_board_id,
            "user_id": sample_user_id,
            "max_out_tokens": 1500,
            "model": "GPT-4"
        }
        
        expected_response = {
            "draft_md": "# 서론\n내용...\n\n# 본론\n내용...\n\n# 결론\n내용...",
            "outline_used": ["서론", "본론", "결론"],
            "usage": {
                "in": 150,
                "cached_in": 0,
                "out": 500,
                "embed": 0,
                "total_wtu": 2150
            },
            "routing": {
                "selected_model": "GPT-4",
                "stoploss_triggered": False
            }
        }
        
        mock_board_ai_service.draft_with_model_selection.return_value = expected_response
        
        # When
        response = client.post("/board-ai/draft", json=request_data)
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert "서론" in result["draft_md"]
        assert "본론" in result["draft_md"] 
        assert "결론" in result["draft_md"]
        assert result["outline_used"] == ["서론", "본론", "결론"]
        assert result["usage"]["total_wtu"] == 2150
        
        # 서비스 호출 확인
        mock_board_ai_service.draft_with_model_selection.assert_called_once()
    
    def test_draft_empty_outline(self, mock_board_ai_service, sample_board_id, sample_user_id):
        """POST /board-ai/draft 빈 개요 테스트"""
        # Given
        request_data = {
            "outline": [""],  # 빈 문자열 개요
            "board_id": sample_board_id,
            "user_id": sample_user_id
        }
        
        # 서비스에서 빈 개요 예외 발생 설정
        mock_board_ai_service.draft_with_model_selection.side_effect = ValueError("개요가 비어있습니다.")
        
        # When
        response = client.post("/board-ai/draft", json=request_data)
        
        # Then
        assert response.status_code == 400  # Bad Request
    
    def test_ask_budget_exceeded(self, mock_board_ai_service, sample_board_id, sample_user_id):
        """POST /board-ai/ask 예산 초과 테스트"""
        # Given
        request_data = {
            "query": "예산 초과 질문",
            "board_id": sample_board_id,
            "user_id": sample_user_id,
            "budget_wtu": 100
        }
        
        # 서비스에서 예산 초과 예외 발생 설정
        mock_board_ai_service.ask_with_model_selection.side_effect = ValueError("Budget exceeded: estimated 450 WTU would exceed budget of 100")
        
        # When
        response = client.post("/board-ai/ask", json=request_data)
        
        # Then
        assert response.status_code == 403  # Budget Exceeded
        result = response.json()
        assert "Budget exceeded" in result["detail"]
    
    def test_ask_server_error(self, mock_board_ai_service, sample_board_id, sample_user_id):
        """POST /board-ai/ask 서버 오류 테스트"""
        # Given
        request_data = {
            "query": "서버 오류 발생",
            "board_id": sample_board_id,
            "user_id": sample_user_id
        }
        
        # 서비스에서 일반 예외 발생 설정
        mock_board_ai_service.ask_with_model_selection.side_effect = Exception("Internal service error")
        
        # When
        response = client.post("/board-ai/ask", json=request_data)
        
        # Then
        assert response.status_code == 500  # Internal Server Error
        result = response.json()
        assert "AI 질의 처리 중 오류가 발생했습니다" in result["detail"]