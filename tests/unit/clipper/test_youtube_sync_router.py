import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.collect.v1.clipper.service import get_clipper_service
from app.collect.v1.clipper.schemas_youtube import YouTubeSyncResponse

# TestClient 인스턴스 생성
client = TestClient(app)


@pytest.fixture
def mock_clipper_service():
    """ClipperService를 모의(Mock) 객체로 만들고 의존성을 오버라이드합니다."""
    mock_service = AsyncMock()
    
    # sync_youtube 메서드가 YouTubeSyncResponse를 반환하도록 설정
    mock_service.sync_youtube.return_value = YouTubeSyncResponse(
        success=True,
        message="YouTube 동영상이 성공적으로 저장되었습니다."
    )
    
    # 의존성 오버라이드 설정
    app.dependency_overrides[get_clipper_service] = lambda: mock_service
    
    yield mock_service
    
    # 테스트 후 의존성 오버라이드 정리
    app.dependency_overrides.clear()


class TestYouTubeSyncRouter:
    """YouTube 동영상 저장 Router 단위 테스트"""
    
    def test_sync_youtube_success(self, mock_clipper_service):
        """POST /api/v1/clipper/youtube/sync 엔드포인트 성공 테스트"""
        # Given
        form_data = {
            "item_id": 12345,
            "user_id": 67890,
            "thumbnail": "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
            "title": "테스트 YouTube 동영상",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "summary": "이것은 테스트용 YouTube 동영상입니다.",
            "tags": ["테스트", "YouTube", "동영상"],
            "category": "Education",
            "memo": "테스트용 메모입니다.",
            "transcript": "안녕하세요. 이것은 테스트 YouTube 동영상의 스크립트입니다. 오늘은 테스트에 대해 알아보겠습니다."
        }
        
        # Mock 서비스가 이미 fixture에서 설정됨 - 추가 설정 불필요
        
        # When
        response = client.post("/api/v1/clipper/youtube/sync", data=form_data)
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert result["success"] == True
        assert result["message"] == "YouTube 동영상이 성공적으로 동기화되었습니다."
        
        # 서비스 호출 확인
        mock_clipper_service.sync_youtube.assert_called_once()
        
        # 호출된 인자 확인
        call_args = mock_clipper_service.sync_youtube.call_args
        args, kwargs = call_args
        
        # 첫 번째는 session, 두 번째는 background_tasks, 세 번째는 request_data
        assert len(args) == 3
        request_data = args[2]
        
        assert request_data.item_id == form_data["item_id"]
        assert request_data.user_id == form_data["user_id"]
        assert request_data.title == form_data["title"]
        assert request_data.url == form_data["url"]
        assert request_data.transcript == form_data["transcript"]
        assert request_data.category == form_data["category"]
    
    def test_sync_youtube_validation_error(self, mock_clipper_service):
        """POST /api/v1/clipper/youtube/sync 유효성 검증 실패 테스트"""
        # Given - 필수 필드 누락
        form_data = {
            "item_id": 12345,
            "user_id": 67890,
            "title": "테스트 YouTube 동영상",
            # url 누락
            # thumbnail 누락
            # category 누락
            # transcript 누락
        }
        
        # When
        response = client.post("/api/v1/clipper/youtube/sync", data=form_data)
        
        # Then
        assert response.status_code == 422  # Validation Error
        
        # 서비스가 호출되지 않았는지 확인
        mock_clipper_service.sync_youtube.assert_not_called()
    
    def test_sync_youtube_service_error(self, mock_clipper_service):
        """POST /api/v1/clipper/youtube/sync 서비스 오류 테스트"""
        # Given
        form_data = {
            "item_id": 12345,
            "user_id": 67890,
            "thumbnail": "https://img.youtube.com/vi/test/maxresdefault.jpg",
            "title": "테스트 동영상",
            "url": "https://www.youtube.com/watch?v=test123",
            "category": "Education",
            "transcript": "테스트 스크립트"
        }
        
        # 서비스에서 예외 발생 설정
        mock_clipper_service.sync_youtube.side_effect = Exception("Database connection failed")
        
        # When
        response = client.post("/api/v1/clipper/youtube/sync", data=form_data)
        
        # Then
        assert response.status_code == 500  # Internal Server Error
        result = response.json()
        assert "Database connection failed" in result["detail"]
    
    def test_sync_youtube_optional_fields(self, mock_clipper_service):
        """POST /api/v1/clipper/youtube/sync 선택적 필드 테스트"""
        # Given - 필수 필드만 포함
        form_data = {
            "item_id": 99999,
            "user_id": 11111,
            "thumbnail": "https://img.youtube.com/vi/minimal/maxresdefault.jpg",
            "title": "최소한의 YouTube 동영상",
            "url": "https://www.youtube.com/watch?v=minimal123",
            "category": "Entertainment",
            "transcript": "최소한의 스크립트 내용입니다."
            # summary, tags, memo는 선택적이므로 제외
        }
        
        # Mock 서비스가 이미 fixture에서 설정됨 - 추가 설정 불필요
        
        # When
        response = client.post("/api/v1/clipper/youtube/sync", data=form_data)
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert result["success"] == True
        
        # 서비스 호출 시 선택적 필드가 None 또는 빈 리스트로 설정되었는지 확인
        call_args = mock_clipper_service.sync_youtube.call_args
        args, kwargs = call_args
        request_data = args[2]
        
        assert request_data.summary is None
        assert request_data.tags == []  # 기본값으로 빈 리스트 설정
        assert request_data.memo is None
    
    def test_sync_youtube_long_transcript(self, mock_clipper_service):
        """POST /api/v1/clipper/youtube/sync 긴 스크립트 처리 테스트"""
        # Given
        long_transcript = "이것은 매우 긴 YouTube 스크립트입니다. " * 500  # 긴 텍스트 생성
        
        form_data = {
            "item_id": 88888,
            "user_id": 22222,
            "thumbnail": "https://img.youtube.com/vi/longvideo/maxresdefault.jpg",
            "title": "긴 스크립트를 가진 동영상",
            "url": "https://www.youtube.com/watch?v=longvideo123",
            "category": "Tutorial",
            "transcript": long_transcript
        }
        
        # Mock 서비스가 이미 fixture에서 설정됨 - 추가 설정 불필요
        
        # When
        response = client.post("/api/v1/clipper/youtube/sync", data=form_data)
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert result["success"] == True
        
        # 긴 스크립트가 정상적으로 전달되었는지 확인
        call_args = mock_clipper_service.sync_youtube.call_args
        args, kwargs = call_args
        request_data = args[2]
        assert len(request_data.transcript) == len(long_transcript)
        assert request_data.transcript == long_transcript
    
    def test_sync_youtube_update_scenario(self, mock_clipper_service):
        """POST /api/v1/clipper/youtube/sync 기존 아이템 업데이트 시나리오 테스트"""
        # Given - 기존 item_id로 업데이트 요청
        form_data = {
            "item_id": 1,  # 기존 아이템 ID
            "user_id": 1,
            "thumbnail": "https://img.youtube.com/vi/updated/maxresdefault.jpg",
            "title": "업데이트된 동영상 제목",
            "url": "https://www.youtube.com/watch?v=updated123",
            "summary": "업데이트된 요약입니다.",
            "tags": ["업데이트", "수정", "테스트"],
            "category": "Technology",
            "memo": "업데이트된 메모입니다.",
            "transcript": "업데이트된 스크립트 내용입니다."
        }
        
        # Mock 서비스가 이미 fixture에서 설정됨 - 추가 설정 불필요
        
        # When
        response = client.post("/api/v1/clipper/youtube/sync", data=form_data)
        
        # Then
        assert response.status_code == 200
        result = response.json()
        assert result["success"] == True
        
        # 업데이트된 데이터가 정상적으로 전달되었는지 확인
        call_args = mock_clipper_service.sync_youtube.call_args
        args, kwargs = call_args
        request_data = args[2]
        
        assert request_data.item_id == 1
        assert request_data.title == "업데이트된 동영상 제목"
        assert request_data.summary == "업데이트된 요약입니다."
        assert "업데이트" in request_data.tags
        assert request_data.memo == "업데이트된 메모입니다."