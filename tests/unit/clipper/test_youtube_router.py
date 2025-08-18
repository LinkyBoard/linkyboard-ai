import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.collect.v1.clipper.service import get_clipper_service

# TestClient 인스턴스 생성
client = TestClient(app)


@pytest.fixture
def mock_clipper_service():
    """ClipperService를 모의(Mock) 객체로 만들고 의존성을 오버라이드합니다."""
    mock_service = AsyncMock()
    
    # 의존성 오버라이드 설정
    app.dependency_overrides[get_clipper_service] = lambda: mock_service
    
    yield mock_service
    
    # 테스트 후 의존성 오버라이드 정리
    app.dependency_overrides.clear()


class TestYouTubeRouter:
    """YouTube 요약 Router 단위 테스트"""
    
    def test_summarize_youtube_success(self, mock_clipper_service):
        """POST /api/v1/clipper/youtube/summarize 엔드포인트 성공 테스트"""
        # Given
        form_data = {
            "url": "https://www.youtube.com/watch?v=test123",
            "title": "테스트 유튜브 동영상",
            "transcript": "안녕하세요. 이것은 테스트 유튜브 동영상의 스크립트입니다. 여기에는 동영상의 주요 내용이 포함되어 있습니다.",
            "user_id": 12345,
            "tag_count": 5
        }
        
        expected_response = {
            'summary': '이 동영상은 테스트 목적으로 제작된 콘텐츠로, 주요 메시지와 핵심 정보를 포함하고 있습니다.',
            'recommended_tags': ['테스트', '유튜브', '동영상', '콘텐츠', '교육'],
            'recommended_category': 'Education'
        }
        
        mock_clipper_service.generate_youtube_summary_with_recommendations.return_value = expected_response
        
        # When
        response = client.post("/api/v1/clipper/youtube/summarize", data=form_data)
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert result["summary"] == expected_response['summary']
        assert result["tags"] == expected_response['recommended_tags']
        assert result["category"] == expected_response['recommended_category']
        
        # 서비스 호출 확인
        mock_clipper_service.generate_youtube_summary_with_recommendations.assert_called_once()
        call_args = mock_clipper_service.generate_youtube_summary_with_recommendations.call_args[1]
        assert call_args["url"] == form_data["url"]
        assert call_args["title"] == form_data["title"]
        assert call_args["transcript"] == form_data["transcript"]
        assert call_args["user_id"] == form_data["user_id"]
        assert call_args["tag_count"] == form_data["tag_count"]
    
    def test_summarize_youtube_validation_error(self, mock_clipper_service):
        """POST /api/v1/clipper/youtube/summarize 유효성 검증 실패 테스트"""
        # Given - 필수 필드 누락
        form_data = {
            "url": "https://www.youtube.com/watch?v=test123",
            "title": "테스트 유튜브 동영상",
            # transcript 누락
            "user_id": 12345
        }
        
        # When
        response = client.post("/api/v1/clipper/youtube/summarize", data=form_data)
        
        # Then
        assert response.status_code == 422  # Validation Error
        
        # 서비스가 호출되지 않았는지 확인
        mock_clipper_service.generate_youtube_summary_with_recommendations.assert_not_called()
    
    def test_summarize_youtube_service_error(self, mock_clipper_service):
        """POST /api/v1/clipper/youtube/summarize 서비스 오류 테스트"""
        # Given
        form_data = {
            "url": "https://www.youtube.com/watch?v=test123",
            "title": "테스트 유튜브 동영상",
            "transcript": "테스트 스크립트 내용",
            "user_id": 12345
        }
        
        # 서비스에서 예외 발생 설정
        mock_clipper_service.generate_youtube_summary_with_recommendations.side_effect = Exception("AI service unavailable")
        
        # When
        response = client.post("/api/v1/clipper/youtube/summarize", data=form_data)
        
        # Then
        assert response.status_code == 500  # Internal Server Error
        result = response.json()
        assert "유튜브 요약 생성 중 오류가 발생했습니다" in result["detail"]
    
    def test_summarize_youtube_with_default_tag_count(self, mock_clipper_service):
        """POST /api/v1/clipper/youtube/summarize tag_count 기본값 테스트"""
        # Given
        form_data = {
            "url": "https://www.youtube.com/watch?v=test123",
            "title": "테스트 동영상",
            "transcript": "테스트 스크립트",
            "user_id": 12345
            # tag_count 생략 (기본값 5 사용)
        }
        
        expected_response = {
            'summary': '테스트 요약',
            'recommended_tags': ['태그1', '태그2', '태그3', '태그4', '태그5'],
            'recommended_category': 'Education'
        }
        
        mock_clipper_service.generate_youtube_summary_with_recommendations.return_value = expected_response
        
        # When
        response = client.post("/api/v1/clipper/youtube/summarize", data=form_data)
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert len(result["tags"]) == 5
        
        # 서비스 호출 시 기본값 확인
        call_args = mock_clipper_service.generate_youtube_summary_with_recommendations.call_args[1]
        assert call_args["tag_count"] == 5
    
    def test_summarize_youtube_long_transcript(self, mock_clipper_service):
        """POST /api/v1/clipper/youtube/summarize 긴 스크립트 처리 테스트"""
        # Given
        long_transcript = "이것은 매우 긴 유튜브 스크립트입니다. " * 200  # 긴 텍스트 생성
        
        form_data = {
            "url": "https://www.youtube.com/watch?v=test123",
            "title": "긴 동영상 제목",
            "transcript": long_transcript,
            "user_id": 12345
        }
        
        expected_response = {
            'summary': '이 긴 동영상은 여러 주제를 다루며 많은 정보를 제공합니다.',
            'recommended_tags': ['긴동영상', '정보', '교육', '상세설명', '튜토리얼'],
            'recommended_category': 'Tutorial'
        }
        
        mock_clipper_service.generate_youtube_summary_with_recommendations.return_value = expected_response
        
        # When
        response = client.post("/api/v1/clipper/youtube/summarize", data=form_data)
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert result["summary"] == expected_response['summary']
        assert result["category"] == expected_response['recommended_category']
        
        # 긴 스크립트가 서비스로 전달되었는지 확인
        call_args = mock_clipper_service.generate_youtube_summary_with_recommendations.call_args[1]
        assert len(call_args["transcript"]) == len(long_transcript)