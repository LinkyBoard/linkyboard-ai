"""
YouTube URL 추출기 단위 테스트
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.ai.content_extraction.youtube_url_extractor import YouTubeUrlExtractor


class TestYouTubeUrlExtractor:
    """YouTube URL 추출기 테스트"""
    
    @pytest.fixture
    def extractor(self):
        """추출기 인스턴스 생성"""
        return YouTubeUrlExtractor()
    
    def test_extract_video_id_valid_urls(self, extractor):
        """유효한 YouTube URL에서 비디오 ID 추출 테스트"""
        test_cases = [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/v/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ]
        
        for url, expected_id in test_cases:
            result = extractor.extract_video_id(url)
            assert result == expected_id, f"Failed for URL: {url}"
    
    def test_extract_video_id_invalid_urls(self, extractor):
        """잘못된 URL에서 비디오 ID 추출 실패 테스트"""
        invalid_urls = [
            "https://www.google.com",
            "https://www.youtube.com/user/channel",
            "not_a_url",
            "",
            "https://www.youtube.com/watch?v=",
        ]
        
        for url in invalid_urls:
            result = extractor.extract_video_id(url)
            assert result is None, f"Should return None for invalid URL: {url}"
    
    def test_is_valid_youtube_url(self, extractor):
        """YouTube URL 유효성 검사 테스트"""
        valid_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        ]
        
        invalid_urls = [
            "https://www.google.com",
            "not_a_url",
            "",
            "https://www.youtube.com/channel/UCtest",
        ]
        
        for url in valid_urls:
            assert extractor._is_valid_youtube_url(url), f"Should be valid: {url}"
        
        for url in invalid_urls:
            assert not extractor._is_valid_youtube_url(url), f"Should be invalid: {url}"
    
    def test_format_duration(self, extractor):
        """비디오 길이 포맷팅 테스트"""
        test_cases = [
            (30, "00:30"),
            (90, "01:30"),
            (3600, "01:00:00"),
            (3661, "01:01:01"),
            (7263, "02:01:03"),
        ]
        
        for seconds, expected in test_cases:
            result = extractor._format_duration(seconds)
            assert result == expected, f"Duration {seconds} should format as {expected}, got {result}"
    
    def test_format_upload_date(self, extractor):
        """업로드 날짜 포맷팅 테스트"""
        test_cases = [
            ("20231225", "2023-12-25"),
            ("20240101", "2024-01-01"),
            ("invalid", "invalid"),
            ("", ""),
        ]
        
        for date_str, expected in test_cases:
            result = extractor._format_upload_date(date_str)
            assert result == expected, f"Date {date_str} should format as {expected}, got {result}"
    
    @pytest.mark.asyncio
    @patch('app.ai.content_extraction.youtube_url_extractor.yt_dlp.YoutubeDL')
    async def test_extract_video_metadata_success(self, mock_ydl_class, extractor):
        """비디오 메타데이터 성공적 추출 테스트"""
        # Mock 설정
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        
        mock_video_info = {
            'id': 'dQw4w9WgXcQ',
            'title': 'Test Video',
            'description': 'Test description',
            'uploader': 'Test Channel',
            'channel': 'Test Channel',
            'upload_date': '20231225',
            'duration': 180,
            'view_count': 1000,
            'like_count': 100,
            'thumbnail': 'https://example.com/thumb.jpg',
            'thumbnails': [
                {'url': 'https://example.com/thumb.jpg', 'width': 1280, 'height': 720}
            ],
            'tags': ['test', 'video'],
            'categories': ['Entertainment'],
            'language': 'en',
            'availability': 'public'
        }
        
        mock_ydl.extract_info.return_value = mock_video_info
        
        # 테스트 실행
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = await extractor.extract_video_metadata(url)
        
        # 검증
        assert result['video_id'] == 'dQw4w9WgXcQ'
        assert result['title'] == 'Test Video'
        assert result['duration_formatted'] == '03:00'
        assert result['upload_date_formatted'] == '2023-12-25'
        assert result['best_thumbnail'] == 'https://example.com/thumb.jpg'
        assert 'error' not in result
    
    @pytest.mark.asyncio
    @patch('app.ai.content_extraction.youtube_url_extractor.yt_dlp.YoutubeDL')
    async def test_extract_video_metadata_failure(self, mock_ydl_class, extractor):
        """비디오 메타데이터 추출 실패 테스트"""
        # Mock 설정
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = Exception("Video unavailable")
        
        # 테스트 실행
        url = "https://www.youtube.com/watch?v=invalid"
        result = await extractor.extract_video_metadata(url)
        
        # 검증
        assert result['video_id'] is None
        assert result['title'] == 'Unknown YouTube Video'
        assert 'error' in result
        # URL이 잘못된 경우 "올바르지 않은 YouTube URL" 메시지가 나올 수 있음
        assert ('비디오를 사용할 수 없습니다' in result['error'] or 
                '올바르지 않은 YouTube URL' in result['error'] or
                'Video unavailable' in result['error'])
    
    @pytest.mark.asyncio
    @patch('app.ai.content_extraction.youtube_url_extractor.YouTubeTranscriptApi')
    async def test_extract_transcript_success(self, mock_transcript_api_class, extractor):
        """자막 추출 성공 테스트"""
        # Mock API 인스턴스
        mock_api = Mock()
        mock_transcript_api_class.return_value = mock_api
        
        # Mock transcript
        mock_transcript = Mock()
        mock_transcript.language = 'Korean'
        mock_transcript.language_code = 'ko' 
        mock_transcript.is_generated = False
        
        transcript_data = [
            {'text': '안녕하세요 테스트입니다', 'start': 0.0, 'duration': 2.0}
        ]
        mock_transcript.fetch.return_value = transcript_data
        
        # Mock transcript list
        mock_transcripts = Mock()
        mock_transcripts.__iter__ = Mock(return_value=iter([mock_transcript]))
        mock_api.list.return_value = mock_transcripts
        
        # 테스트 실행
        result = await extractor.extract_transcript('dQw4w9WgXcQ')
        
        # 검증
        assert result['success'] is True
        assert result['video_id'] == 'dQw4w9WgXcQ'
        assert result['language'] == 'ko'
        assert result['is_auto_generated'] is False
        assert '안녕하세요 테스트입니다' in result['transcript']
    
    @pytest.mark.asyncio
    @patch('app.ai.content_extraction.youtube_url_extractor.YouTubeTranscriptApi')
    async def test_extract_transcript_failure(self, mock_transcript_api_class, extractor):
        """자막 추출 실패 테스트"""
        # Mock API 인스턴스
        mock_api = Mock()
        mock_transcript_api_class.return_value = mock_api
        mock_api.list.side_effect = Exception("No transcript found")
        
        # 테스트 실행
        result = await extractor.extract_transcript('invalid_id')
        
        # 검증
        assert result['success'] is False
        assert result['video_id'] == 'invalid_id'
        assert 'error' in result
    
    @pytest.mark.asyncio
    @patch.object(YouTubeUrlExtractor, 'extract_video_metadata')
    @patch.object(YouTubeUrlExtractor, 'extract_transcript')
    @patch.object(YouTubeUrlExtractor, 'extract_video_id')
    async def test_extract_complete_info_success(
        self, mock_extract_id, mock_extract_transcript, mock_extract_metadata, extractor
    ):
        """완전한 정보 추출 성공 테스트"""
        # Mock 설정
        mock_extract_id.return_value = 'dQw4w9WgXcQ'
        mock_extract_metadata.return_value = {'title': 'Test Video', 'video_id': 'dQw4w9WgXcQ'}
        mock_extract_transcript.return_value = {
            'success': True,
            'transcript': 'Test transcript',
            'language': 'ko'
        }
        
        # 테스트 실행
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = await extractor.extract_complete_info(url)
        
        # 검증
        assert result['extraction_success'] is True
        assert result['url'] == url
        assert 'metadata' in result
        assert 'transcript' in result
        assert 'combined_content' in result
        assert 'extraction_timestamp' in result
    
    @pytest.mark.asyncio
    @patch.object(YouTubeUrlExtractor, 'extract_video_id')
    async def test_extract_complete_info_invalid_url(self, mock_extract_id, extractor):
        """잘못된 URL로 완전한 정보 추출 실패 테스트"""
        # Mock 설정
        mock_extract_id.return_value = None
        
        # 테스트 실행
        url = "https://invalid-url.com"
        result = await extractor.extract_complete_info(url)
        
        # 검증
        assert result['extraction_success'] is False
        assert 'error' in result
        assert result['url'] == url
    
    def test_create_combined_content(self, extractor):
        """결합된 콘텐츠 생성 테스트"""
        metadata = {
            'title': 'Test Video',
            'description': 'This is a test video description'
        }
        
        transcript_info = {
            'transcript': 'Hello, this is a test transcript'
        }
        
        result = extractor._create_combined_content(metadata, transcript_info)
        
        assert 'Test Video' in result
        assert 'This is a test video description' in result
        assert 'Hello, this is a test transcript' in result
    
    def test_get_empty_metadata_result(self, extractor):
        """빈 메타데이터 결과 테스트"""
        url = "https://www.youtube.com/watch?v=test"
        result = extractor._get_empty_metadata_result(url)
        
        assert result['video_id'] is None
        assert result['title'] == 'Unknown YouTube Video'
        assert result['uploader'] == 'Unknown'
        assert result['duration'] is None
        assert result['duration_formatted'] == "Unknown"
    
    def test_analyze_metadata_error(self, extractor):
        """메타데이터 오류 분석 테스트"""
        test_cases = [
            ("Video unavailable", "비디오를 사용할 수 없습니다"),
            ("Invalid YouTube URL format", "올바르지 않은 YouTube URL 형식"),
            ("Sign in to confirm your age", "연령 제한이 있는 비디오"),
            ("Network timeout error", "네트워크 연결 문제"),
            ("403 Blocked", "YouTube에서 액세스가 차단"),
            ("Region restricted content", "지역 제한으로 인해")
        ]
        
        for original_error, expected_keyword in test_cases:
            user_error, suggestions = extractor._analyze_metadata_error(original_error, "test_url")
            assert expected_keyword in user_error
            assert len(suggestions) > 0
            assert all(isinstance(s, str) for s in suggestions)
    
    def test_analyze_transcript_error(self, extractor):
        """자막 오류 분석 테스트"""
        test_cases = [
            ("No transcript available", "자막이 제공되지 않습니다"),
            ("Transcript disabled by uploader", "자막이 비활성화되어 있습니다"),
            ("YouTube Transcript API error", "YouTube 자막 서비스에 연결할 수 없습니다"),
            ("Could not retrieve transcript data", "자막 데이터를 가져올 수 없습니다")
        ]
        
        for original_error, expected_keyword in test_cases:
            user_error, suggestions = extractor._analyze_transcript_error(original_error, "test_video_id")
            assert expected_keyword in user_error
            assert len(suggestions) > 0
            assert all(isinstance(s, str) for s in suggestions)
    
    @pytest.mark.asyncio
    @patch('app.ai.content_extraction.youtube_url_extractor.YouTubeTranscriptApi')
    async def test_extract_transcript_with_auto_generated(self, mock_transcript_api_class, extractor):
        """자동 생성 자막 추출 테스트"""
        # Mock API 인스턴스 생성
        mock_api = Mock()
        mock_transcript_api_class.return_value = mock_api
        
        # Mock 수동 자막 (한국어 없음)
        mock_manual_transcript = Mock()
        mock_manual_transcript.language_code = 'en'
        mock_manual_transcript.language = 'English'
        mock_manual_transcript.is_generated = False
        
        # Mock 자동 자막 (한국어 있음)
        mock_auto_transcript = Mock()
        mock_auto_transcript.language_code = 'ko'
        mock_auto_transcript.language = 'Korean'
        mock_auto_transcript.is_generated = True
        mock_auto_transcript.fetch.return_value = [
            {'text': '자동 생성된 자막 내용입니다', 'start': 0.0, 'duration': 2.0}
        ]
        
        # Mock transcript list
        mock_transcripts = Mock()
        mock_transcripts.__iter__ = Mock(return_value=iter([mock_manual_transcript, mock_auto_transcript]))
        mock_api.list.return_value = mock_transcripts
        
        # 테스트 실행
        result = await extractor.extract_transcript('test_video_id', ['ko'])
        
        # 검증
        assert result['success'] is True
        assert result['language'] == 'ko'
        assert result['is_auto_generated'] is True
        assert result['extraction_method'] == 'auto_ko'
        assert '자동 생성된 자막 내용입니다' in result['transcript']
    
    @pytest.mark.asyncio
    @patch('app.ai.content_extraction.youtube_url_extractor.YouTubeTranscriptApi')
    async def test_extract_transcript_with_translation(self, mock_transcript_api_class, extractor):
        """번역 자막 추출 테스트"""
        # Mock API 인스턴스 생성
        mock_api = Mock()
        mock_transcript_api_class.return_value = mock_api
        
        # Mock 영어 자막 (번역 가능)
        mock_english_transcript = Mock()
        mock_english_transcript.language_code = 'en'
        mock_english_transcript.language = 'English'
        mock_english_transcript.is_generated = False
        mock_english_transcript.translate = Mock()
        
        mock_translated = Mock()
        mock_translated.fetch.return_value = [
            {'text': '번역된 자막 내용입니다', 'start': 0.0, 'duration': 2.0}
        ]
        mock_english_transcript.translate.return_value = mock_translated
        
        mock_transcripts = Mock()
        mock_transcripts.__iter__ = Mock(return_value=iter([mock_english_transcript]))
        mock_api.list.return_value = mock_transcripts
        
        # 테스트 실행 - 한국어 자막이 없어서 번역 시도
        result = await extractor.extract_transcript('test_video_id', ['ko'])
        
        # 검증
        assert result['success'] is True
        assert result['language'] == 'ko'
        assert result['is_auto_generated'] is True
        assert result['extraction_method'] == 'translated_ko_from_en'
        assert '번역된 자막 내용입니다' in result['transcript']