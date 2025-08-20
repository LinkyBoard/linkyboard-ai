"""
YouTube URL API 기능 테스트
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app


class TestYouTubeUrlApi:
    """YouTube URL API 테스트"""
    
    @pytest.fixture
    def client(self):
        """테스트 클라이언트 생성"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock 데이터베이스 세션"""
        return AsyncMock()
    
    @pytest.fixture
    def sample_request_data(self):
        """샘플 요청 데이터"""
        return {
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "user_id": 1,
            "tag_count": 5
        }
    
    @pytest.fixture
    def sample_success_response(self):
        """샘플 성공 응답 데이터"""
        return {
            'success': True,
            'video_info': {
                'video_id': 'dQw4w9WgXcQ',
                'title': 'Test YouTube Video',
                'description': 'Test description',
                'uploader': 'Test Channel',
                'duration_formatted': '03:32',
                'upload_date_formatted': '2023-12-25',
                'view_count': 1000000,
                'like_count': 50000
            },
            'transcript_info': {
                'success': True,
                'transcript': 'This is a test transcript',
                'language': 'en',
                'is_auto_generated': False,
                'word_count': 5,
                'char_count': 25
            },
            'summary': 'This is a test video summary',
            'tags': ['test', 'video', 'youtube'],
            'category': 'Education',
            'extraction_metadata': {
                'extraction_timestamp': '2023-12-25T12:00:00',
                'transcript_language': 'en',
                'is_auto_generated': False
            }
        }
    
    @patch('app.collect.v1.clipper.service.get_clipper_service')
    @patch('app.core.database.get_db')
    def test_analyze_youtube_url_success(
        self, mock_get_db, mock_get_service, client, mock_db_session, 
        sample_request_data, sample_success_response
    ):
        """YouTube URL 분석 성공 테스트"""
        # Mock 설정
        mock_get_db.return_value = mock_db_session
        mock_service = AsyncMock()
        mock_service.generate_youtube_summary_from_url.return_value = sample_success_response
        mock_get_service.return_value = mock_service
        
        # API 호출
        response = client.post("/api/v1/clipper/youtube/analyze-url", json=sample_request_data)
        
        # 검증
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is True
        assert data['video_info']['video_id'] == 'dQw4w9WgXcQ'
        assert data['video_info']['title'] == 'Test YouTube Video'
        assert data['transcript_info']['success'] is True
        assert data['summary'] == 'This is a test video summary'
        assert len(data['tags']) == 3
        assert data['category'] == 'Education'
        assert data['error'] is None
    
    @patch('app.collect.v1.clipper.service.get_clipper_service')
    @patch('app.core.database.get_db')
    def test_analyze_youtube_url_extraction_failure(
        self, mock_get_db, mock_get_service, client, mock_db_session, sample_request_data
    ):
        """YouTube URL 분석 실패 테스트 - 추출 실패"""
        # Mock 설정
        mock_get_db.return_value = mock_db_session
        mock_service = AsyncMock()
        mock_service.generate_youtube_summary_from_url.return_value = {
            'success': False,
            'error': '비디오를 사용할 수 없습니다 (비공개 또는 삭제됨)',
            'video_info': None,
            'transcript_info': None,
            'summary': None,
            'tags': None,
            'category': None
        }
        mock_get_service.return_value = mock_service
        
        # API 호출
        response = client.post("/api/v1/clipper/youtube/analyze-url", json=sample_request_data)
        
        # 검증
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is False
        assert '비디오를 사용할 수 없습니다' in data['error']
        assert data['video_info'] is None
        assert data['transcript_info'] is None
        assert data['summary'] is None
        assert data['tags'] is None
        assert data['category'] is None
    
    @patch('app.collect.v1.clipper.service.get_clipper_service')
    @patch('app.core.database.get_db')
    def test_analyze_youtube_url_no_transcript(
        self, mock_get_db, mock_get_service, client, mock_db_session, sample_request_data
    ):
        """YouTube URL 분석 실패 테스트 - 자막 없음"""
        # Mock 설정
        mock_get_db.return_value = mock_db_session
        mock_service = AsyncMock()
        mock_service.generate_youtube_summary_from_url.return_value = {
            'success': False,
            'error': '자막을 사용할 수 없는 동영상입니다.',
            'video_info': {
                'video_id': 'dQw4w9WgXcQ',
                'title': 'Test Video Without Transcript',
                'duration_formatted': '03:32'
            },
            'transcript_info': {
                'success': False,
                'transcript': '',
                'error': 'No transcript available'
            },
            'summary': None,
            'tags': None,
            'category': None
        }
        mock_get_service.return_value = mock_service
        
        # API 호출
        response = client.post("/api/v1/clipper/youtube/analyze-url", json=sample_request_data)
        
        # 검증
        assert response.status_code == 200
        data = response.json()
        
        assert data['success'] is False
        assert '자막을 사용할 수 없는 동영상입니다' in data['error']
        assert data['video_info'] is not None
        assert data['transcript_info']['success'] is False
    
    def test_analyze_youtube_url_invalid_request_data(self, client):
        """잘못된 요청 데이터 테스트"""
        invalid_data = {
            "url": "",  # 빈 URL
            "user_id": "invalid_user_id",  # 잘못된 타입
            # tag_count 누락
        }
        
        response = client.post("/api/v1/clipper/youtube/analyze-url", json=invalid_data)
        
        # 검증 - 422 Validation Error 예상
        assert response.status_code == 422
    
    def test_analyze_youtube_url_missing_required_fields(self, client):
        """필수 필드 누락 테스트"""
        incomplete_data = {
            "user_id": 1
            # url 누락
        }
        
        response = client.post("/api/v1/clipper/youtube/analyze-url", json=incomplete_data)
        
        # 검증 - 422 Validation Error 예상
        assert response.status_code == 422
    
    @patch('app.collect.v1.clipper.service.get_clipper_service')
    @patch('app.core.database.get_db')
    def test_analyze_youtube_url_service_exception(
        self, mock_get_db, mock_get_service, client, mock_db_session, sample_request_data
    ):
        """서비스 레이어 예외 발생 테스트"""
        # Mock 설정
        mock_get_db.return_value = mock_db_session
        mock_service = AsyncMock()
        mock_service.generate_youtube_summary_from_url.side_effect = Exception("Internal service error")
        mock_get_service.return_value = mock_service
        
        # API 호출
        response = client.post("/api/v1/clipper/youtube/analyze-url", json=sample_request_data)
        
        # 검증
        assert response.status_code == 200  # 에러를 응답으로 반환
        data = response.json()
        
        assert data['success'] is False
        assert 'YouTube URL 분석 중 오류가 발생했습니다' in data['error']
    
    def test_analyze_youtube_url_different_url_formats(self, client):
        """다양한 YouTube URL 형식 테스트"""
        url_formats = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ"
        ]
        
        with patch('app.collect.v1.clipper.service.get_clipper_service') as mock_get_service, \
             patch('app.core.database.get_db') as mock_get_db:
            
            mock_get_db.return_value = AsyncMock()
            mock_service = AsyncMock()
            mock_service.generate_youtube_summary_from_url.return_value = {
                'success': True,
                'video_info': {'video_id': 'dQw4w9WgXcQ'},
                'transcript_info': {'success': True},
                'summary': 'Test',
                'tags': ['test'],
                'category': 'Test'
            }
            mock_get_service.return_value = mock_service
            
            for url in url_formats:
                request_data = {
                    "url": url,
                    "user_id": 1,
                    "tag_count": 3
                }
                
                response = client.post("/api/v1/clipper/youtube/analyze-url", json=request_data)
                
                # 모든 URL 형식에 대해 성공적으로 처리되어야 함
                assert response.status_code == 200, f"Failed for URL format: {url}"
                data = response.json()
                assert data['success'] is True, f"Failed for URL format: {url}"