"""
YouTube 스마트 추출 시스템 테스트
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.ai.content_extraction.youtube_extractor import YouTubeContentExtractor
from app.ai.classification.smart_extractor import SmartExtractionService


@pytest.fixture
def sample_youtube_data():
    """테스트용 YouTube 데이터"""
    return {
        'title': 'Python 웹 개발 완전 가이드 | Django vs Flask 비교',
        'transcript': '''
        안녕하세요 여러분, 오늘은 Python을 이용한 웹 개발에 대해서 알아보겠습니다.
        Python은 현재 가장 인기있는 프로그래밍 언어 중 하나입니다.
        특히 웹 개발 분야에서는 Django와 Flask라는 두 개의 주요 프레임워크가 있습니다.
        
        Django는 풀스택 프레임워크로 많은 기능이 내장되어 있습니다.
        반면 Flask는 마이크로 프레임워크로 가볍고 유연합니다.
        
        Django의 장점으로는 관리자 패널, ORM, 인증 시스템이 기본 제공됩니다.
        Flask는 간단한 API 개발이나 작은 프로젝트에 적합합니다.
        
        데이터베이스 연동도 중요한 고려사항입니다.
        Django는 Django ORM을 사용하고, Flask는 SQLAlchemy를 주로 사용합니다.
        
        성능면에서는 두 프레임워크 모두 좋은 성능을 보여줍니다.
        하지만 프로젝트 규모와 요구사항에 따라 선택이 달라질 수 있습니다.
        
        마지막으로 학습 곡선을 고려해보면, Flask가 더 쉽게 시작할 수 있습니다.
        하지만 Django는 더 많은 기능을 제공하므로 큰 프로젝트에 유리합니다.
        ''',
        'video_id': 'dQw4w9WgXcQ',
        'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
    }


@pytest.fixture
def sample_user_history():
    """테스트용 사용자 히스토리"""
    return {
        'tags': ['Python', '웹개발', 'Django', 'Flask', '프로그래밍', 'API', '데이터베이스', 'SQLAlchemy'],
        'categories': ['프로그래밍', '웹개발', 'Python', '튜토리얼']
    }


class TestYouTubeContentExtractor:
    """YouTube 콘텐츠 추출기 테스트"""
    
    def test_basic_content_extraction(self, sample_youtube_data):
        """기본 YouTube 콘텐츠 추출 테스트"""
        extractor = YouTubeContentExtractor()
        
        result = extractor.extract_content(
            title=sample_youtube_data['title'],
            transcript=sample_youtube_data['transcript'],
            video_id=sample_youtube_data['video_id']
        )
        
        # 제목이 정제되었을 수 있으므로 주요 키워드 포함 여부 확인
        assert 'Python' in result['title']
        assert 'Django' in result['title']
        assert 'Flask' in result['title']
        assert 'Python' in result['content']
        assert 'Django' in result['content']
        assert 'Flask' in result['content']
        assert result['word_count'] > 0
        assert result['char_count'] > 0
        assert result['extraction_method'] == 'youtube_native'
        assert result['metadata']['video_id'] == sample_youtube_data['video_id']
        assert result['metadata']['has_title'] is True
        assert result['metadata']['has_transcript'] is True
    
    def test_title_only_extraction(self):
        """제목만 있는 경우 테스트"""
        extractor = YouTubeContentExtractor()
        
        result = extractor.extract_content(
            title="Python Tutorial for Beginners",
            transcript="",
            video_id="abc123"
        )
        
        assert result['title'] == "Python Tutorial for Beginners"
        assert result['content'] == "Python Tutorial for Beginners"
        assert result['metadata']['has_title'] is True
        assert result['metadata']['has_transcript'] is False
        assert result['quality_score'] < 0.5  # 낮은 품질 점수
    
    def test_transcript_only_extraction(self):
        """트랜스크립트만 있는 경우 테스트"""
        extractor = YouTubeContentExtractor()
        
        result = extractor.extract_content(
            title="",
            transcript="이것은 파이썬 프로그래밍에 관한 영상입니다. 웹 개발과 데이터 분석을 다룹니다.",
            video_id="xyz789"
        )
        
        assert result['title'] == "Untitled YouTube Video"
        assert '파이썬' in result['content']
        assert result['metadata']['has_title'] is False
        assert result['metadata']['has_transcript'] is True
    
    def test_empty_content_handling(self):
        """빈 콘텐츠 처리 테스트"""
        extractor = YouTubeContentExtractor()
        
        result = extractor.extract_content(
            title="",
            transcript="",
            video_id=None
        )
        
        assert result['title'] == "Untitled YouTube Video"
        assert result['content'] == ""
        assert result['word_count'] == 0
        assert result['char_count'] == 0
        assert result['quality_score'] == 0.0
    
    def test_content_quality_calculation(self, sample_youtube_data):
        """콘텐츠 품질 점수 계산 테스트"""
        extractor = YouTubeContentExtractor()
        
        result = extractor.extract_content(
            title=sample_youtube_data['title'],
            transcript=sample_youtube_data['transcript']
        )
        
        # 제목과 긴 트랜스크립트가 모두 있으므로 높은 품질 점수를 가져야 함
        assert result['quality_score'] > 0.7
        assert 0.0 <= result['quality_score'] <= 1.0
    
    def test_video_duration_estimation(self, sample_youtube_data):
        """비디오 길이 추정 테스트"""
        extractor = YouTubeContentExtractor()
        
        result = extractor.extract_content(
            title=sample_youtube_data['title'],
            transcript=sample_youtube_data['transcript']
        )
        
        # 트랜스크립트 길이에 따라 적절한 길이가 추정되어야 함
        estimated_duration = result['metadata']['estimated_duration']
        assert '분' in estimated_duration or '시간' in estimated_duration


class TestYouTubeSmartExtraction:
    """YouTube 스마트 추출 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_youtube_smart_extraction_full_process(self, sample_youtube_data, sample_user_history):
        """YouTube 전체 스마트 추출 프로세스 테스트"""
        service = SmartExtractionService()
        
        # Mock 세션과 사용자 히스토리
        mock_session = AsyncMock()
        mock_items = []
        for i, tag in enumerate(sample_user_history['tags'][:3]):
            mock_item = MagicMock()
            mock_item.tags = [tag]
            mock_item.category = sample_user_history['categories'][i % len(sample_user_history['categories'])]
            mock_items.append(mock_item)
        
        mock_session.execute.return_value.fetchall.return_value = mock_items
        
        result = await service.extract_youtube_tags_and_category(
            title=sample_youtube_data['title'],
            transcript=sample_youtube_data['transcript'],
            video_id=sample_youtube_data['video_id'],
            user_id=1001,
            max_tags=5,
            session=mock_session
        )
        
        assert 'tags' in result
        assert 'category' in result
        assert 'metadata' in result
        
        assert len(result['tags']) > 0
        assert result['category'] is not None
        assert result['metadata']['processing_method'] == 'smart_extraction_youtube'
        assert result['metadata']['cost_savings'] is True
        
        # YouTube 메타데이터 확인
        assert 'youtube_metadata' in result['metadata']
        assert result['metadata']['youtube_metadata']['video_id'] == sample_youtube_data['video_id']
        assert result['metadata']['youtube_metadata']['has_transcript'] is True
        
        # 품질 정보 확인
        assert result['metadata']['content_info']['quality_score'] > 0
        assert 'estimated_duration' in result['metadata']['content_info']
    
    @pytest.mark.asyncio
    async def test_youtube_extraction_without_user_history(self, sample_youtube_data):
        """사용자 히스토리 없는 YouTube 추출 테스트"""
        service = SmartExtractionService()
        
        mock_session = AsyncMock()
        mock_session.execute.return_value.fetchall.return_value = []
        
        result = await service.extract_youtube_tags_and_category(
            title=sample_youtube_data['title'],
            transcript=sample_youtube_data['transcript'],
            video_id=sample_youtube_data['video_id'],
            user_id=None,  # 사용자 히스토리 없음
            max_tags=3,
            session=mock_session
        )
        
        assert 'tags' in result
        assert len(result['tags']) > 0
        assert result['metadata']['recommendation_details']['user_history_used'] is False
        
        # Python 관련 키워드가 추출되었는지 확인
        extracted_tags_lower = [tag.lower() for tag in result['tags']]
        assert any('python' in tag for tag in extracted_tags_lower)
    
    @pytest.mark.asyncio
    async def test_youtube_extraction_fallback(self):
        """YouTube 추출 실패 시 fallback 테스트"""
        service = SmartExtractionService()
        
        result = await service.extract_youtube_tags_and_category(
            title="",
            transcript="",
            video_id=None,
            user_id=None,
            max_tags=3,
            session=None
        )
        
        assert 'tags' in result
        assert 'category' in result
        assert result['category'] == '기타'
        assert result['metadata']['processing_method'] == 'fallback'
    
    @pytest.mark.asyncio
    async def test_youtube_extraction_tag_relevance(self, sample_youtube_data):
        """YouTube 추출된 태그 관련성 테스트"""
        service = SmartExtractionService()
        
        result = await service.extract_youtube_tags_and_category(
            title=sample_youtube_data['title'],
            transcript=sample_youtube_data['transcript'],
            user_id=None,
            max_tags=5,
            session=None
        )
        
        tags_lower = [tag.lower() for tag in result['tags']]
        
        # YouTube 콘텐츠에 나오는 주요 키워드들이 태그로 추출되어야 함
        relevant_keywords = ['python', 'django', 'flask', '웹', '프로그래밍', '개발']
        
        # 적어도 하나 이상의 관련 키워드가 포함되어야 함
        has_relevant = any(
            any(keyword in tag for keyword in relevant_keywords)
            for tag in tags_lower
        )
        assert has_relevant, f"No relevant keywords found in tags: {result['tags']}"


class TestYouTubeClipperIntegration:
    """YouTube Clipper 서비스 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_clipper_video_id_extraction(self):
        """Clipper 서비스 비디오 ID 추출 테스트"""
        from app.collect.v1.clipper.service import clipper_service
        
        test_urls = [
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'https://youtu.be/dQw4w9WgXcQ',
            'https://www.youtube.com/embed/dQw4w9WgXcQ',
            'https://www.youtube.com/v/dQw4w9WgXcQ'
        ]
        
        for url in test_urls:
            video_id = clipper_service._extract_video_id_from_url(url)
            assert video_id == 'dQw4w9WgXcQ', f"Failed to extract video ID from {url}"
    
    @pytest.mark.asyncio
    async def test_clipper_youtube_smart_extraction_integration(self, sample_youtube_data):
        """Clipper 서비스 YouTube 스마트 추출 통합 테스트"""
        from app.collect.v1.clipper.service import clipper_service
        
        # Mock 의존성들
        mock_session = AsyncMock()
        mock_session.execute.return_value.fetchall.return_value = []
        
        with patch.object(clipper_service.openai_service, 'generate_youtube_summary', return_value="Mock summary"):
            result = await clipper_service.generate_youtube_summary_with_recommendations(
                session=mock_session,
                url=sample_youtube_data['url'],
                title=sample_youtube_data['title'],
                transcript=sample_youtube_data['transcript'],
                user_id=1001,
                tag_count=3
            )
        
        assert 'summary' in result
        assert 'recommended_tags' in result
        assert 'recommended_category' in result
        assert result['summary'] == "Mock summary"
        assert len(result['recommended_tags']) > 0
        assert result['recommended_category'] is not None


class TestPerformanceAndCostSavings:
    """성능 및 비용 절약 테스트"""
    
    @pytest.mark.asyncio
    async def test_processing_speed_youtube(self, sample_youtube_data):
        """YouTube 처리 속도 테스트"""
        import time
        
        service = SmartExtractionService()
        mock_session = AsyncMock()
        mock_session.execute.return_value.fetchall.return_value = []
        
        start_time = time.time()
        
        result = await service.extract_youtube_tags_and_category(
            title=sample_youtube_data['title'],
            transcript=sample_youtube_data['transcript'],
            video_id=sample_youtube_data['video_id'],
            user_id=None,
            max_tags=5,
            session=mock_session
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # 로컬 처리이므로 매우 빨라야 함 (일반적으로 2초 미만)
        assert processing_time < 3.0
        assert result['metadata']['cost_savings'] is True
    
    def test_cost_efficiency_youtube(self):
        """YouTube 비용 효율성 테스트"""
        service = SmartExtractionService()
        
        stats = service.get_processing_stats()
        
        # YouTube 지원 확인
        assert 'YouTube' in stats['supported_content_types']
        assert stats['youtube_extractor_available'] is True
        assert stats['estimated_cost_savings'] == '90%'
        assert stats['processing_time_improvement'] == '50%'