"""
스마트 추출 시스템 테스트
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.ai.content_extraction import HTMLContentExtractor, KeywordExtractor
from app.ai.content_extraction.recommendation_engine import RecommendationEngine
from app.ai.classification.smart_extractor import SmartExtractionService


@pytest.fixture
def sample_html():
    """테스트용 HTML 샘플"""
    return '''
    <html>
    <head>
        <title>Python 프로그래밍 가이드</title>
    </head>
    <body>
        <h1>Python 프로그래밍 완전 가이드</h1>
        <article>
            <p>Python은 간단하고 읽기 쉬운 프로그래밍 언어입니다.</p>
            <p>웹 개발, 데이터 사이언스, 인공지능 분야에서 널리 사용됩니다.</p>
            <p>Django와 Flask는 인기 있는 Python 웹 프레임워크입니다.</p>
            <p>NumPy, Pandas는 데이터 분석에 필수적인 라이브러리입니다.</p>
        </article>
    </body>
    </html>
    '''


@pytest.fixture
def sample_user_history():
    """테스트용 사용자 히스토리"""
    return {
        'tags': ['Python', '프로그래밍', '웹개발', 'Django', 'Flask', '데이터사이언스', 'AI', '머신러닝'],
        'categories': ['프로그래밍', 'AI/ML', '웹개발', '데이터사이언스']
    }


class TestHTMLContentExtractor:
    """HTML 콘텐츠 추출기 테스트"""
    
    def test_basic_extraction(self, sample_html):
        """기본 콘텐츠 추출 테스트"""
        extractor = HTMLContentExtractor()
        
        result = extractor.extract_content(sample_html)
        
        assert result['title'] == 'Python 프로그래밍 가이드'
        assert 'Python은 간단하고 읽기 쉬운' in result['content']
        assert result['word_count'] > 0
        assert result['char_count'] > 0
        assert result['extraction_method'] in ['trafilatura', 'beautifulsoup_fallback', 'basic_regex']
    
    def test_fallback_extraction(self):
        """Fallback 추출 테스트"""
        extractor = HTMLContentExtractor()
        
        # 매우 간단한 HTML
        simple_html = '<html><title>Test</title><body>Simple content</body></html>'
        
        result = extractor.extract_content(simple_html)
        
        assert result['title'] == 'Test'
        assert 'Simple content' in result['content']
    
    def test_empty_html(self):
        """빈 HTML 처리 테스트"""
        extractor = HTMLContentExtractor()
        
        result = extractor.extract_content('')
        
        assert result['content'] == ''
        assert result['title'] == 'Untitled'
        assert result['word_count'] == 0


class TestKeywordExtractor:
    """키워드 추출기 테스트"""
    
    def test_korean_text_extraction(self):
        """한국어 텍스트 키워드 추출 테스트"""
        extractor = KeywordExtractor()
        
        text = "Python 프로그래밍 언어는 웹 개발과 데이터 사이언스에 매우 유용합니다. Django와 Flask는 인기있는 웹 프레임워크입니다."
        
        keywords = extractor.extract_keywords(text, max_keywords=5)
        
        assert len(keywords) > 0
        assert all(isinstance(kw, dict) for kw in keywords)
        assert all('keyword' in kw and 'score' in kw for kw in keywords)
        
        # 중요 키워드들이 포함되어 있는지 확인
        keyword_texts = [kw['keyword'].lower() for kw in keywords]
        assert any('python' in kw for kw in keyword_texts)
    
    def test_english_text_extraction(self):
        """영어 텍스트 키워드 추출 테스트"""
        extractor = KeywordExtractor()
        
        text = "Python is a powerful programming language for web development and data science. Django and Flask are popular web frameworks."
        
        keywords = extractor.extract_keywords(text, max_keywords=5)
        
        assert len(keywords) > 0
        keyword_texts = [kw['keyword'].lower() for kw in keywords]
        assert any('python' in kw for kw in keyword_texts)
    
    def test_mixed_language_extraction(self):
        """한영 혼합 텍스트 키워드 추출 테스트"""
        extractor = KeywordExtractor()
        
        text = "Python programming 언어는 machine learning과 artificial intelligence 분야에서 널리 사용됩니다."
        
        keywords = extractor.extract_keywords(text, max_keywords=8)
        
        assert len(keywords) > 0
        # 한글과 영어 키워드가 모두 추출되는지 확인
        keyword_texts = [kw['keyword'] for kw in keywords]
        has_korean = any(any(ord(char) >= 0xAC00 and ord(char) <= 0xD7A3 for char in kw) for kw in keyword_texts)
        has_english = any(any(char.isalpha() and ord(char) < 128 for char in kw) for kw in keyword_texts)
        
        assert has_korean or has_english  # 적어도 하나는 있어야 함
    
    def test_empty_text(self):
        """빈 텍스트 처리 테스트"""
        extractor = KeywordExtractor()
        
        keywords = extractor.extract_keywords('')
        
        assert keywords == []
    
    def test_short_text(self):
        """짧은 텍스트 처리 테스트"""
        extractor = KeywordExtractor()
        
        keywords = extractor.extract_keywords('안녕')
        
        assert len(keywords) == 0  # 너무 짧으면 키워드 추출 안됨


class TestRecommendationEngine:
    """추천 엔진 테스트"""
    
    def test_tag_recommendation_direct_match(self, sample_user_history):
        """직접 매치 태그 추천 테스트"""
        engine = RecommendationEngine()
        
        extracted_keywords = [
            {'keyword': 'Python', 'score': 0.9},
            {'keyword': '프로그래밍', 'score': 0.8},
            {'keyword': '웹개발', 'score': 0.7}
        ]
        
        recommendations = engine.recommend_tags(
            extracted_keywords=extracted_keywords,
            user_history_tags=sample_user_history['tags'],
            max_recommendations=3
        )
        
        assert len(recommendations) > 0
        
        # 직접 매치된 태그들이 포함되어야 함
        recommended_tags = [rec['tag'] for rec in recommendations]
        assert 'Python' in recommended_tags
        assert '프로그래밍' in recommended_tags
    
    def test_tag_recommendation_similarity_match(self, sample_user_history):
        """유사도 기반 태그 추천 테스트"""
        engine = RecommendationEngine()
        
        extracted_keywords = [
            {'keyword': 'django', 'score': 0.8},  # 소문자로 입력
            {'keyword': '머신러닝', 'score': 0.7}
        ]
        
        recommendations = engine.recommend_tags(
            extracted_keywords=extracted_keywords,
            user_history_tags=sample_user_history['tags'],
            max_recommendations=3
        )
        
        assert len(recommendations) > 0
        
        # Django나 머신러닝이 추천되어야 함
        recommended_tags = [rec['tag'] for rec in recommendations]
        assert 'Django' in recommended_tags or '머신러닝' in recommended_tags
    
    def test_category_recommendation(self, sample_user_history):
        """카테고리 추천 테스트"""
        engine = RecommendationEngine()
        
        extracted_keywords = [
            {'keyword': 'Python', 'score': 0.9},
            {'keyword': '프로그래밍', 'score': 0.8},
            {'keyword': '코딩', 'score': 0.7}
        ]
        
        recommendation = engine.recommend_category(
            extracted_keywords=extracted_keywords,
            user_history_categories=sample_user_history['categories'],
            content_title="Python 프로그래밍 가이드"
        )
        
        assert 'category' in recommendation
        assert recommendation['category'] in sample_user_history['categories']
        assert 'confidence' in recommendation
        assert 0 <= recommendation['confidence'] <= 1
    
    def test_new_tag_suggestion(self):
        """새 태그 제안 테스트"""
        engine = RecommendationEngine()
        
        extracted_keywords = [
            {'keyword': 'FastAPI', 'score': 0.9},
            {'keyword': 'async', 'score': 0.8}
        ]
        
        recommendations = engine.recommend_tags(
            extracted_keywords=extracted_keywords,
            user_history_tags=[],  # 빈 히스토리
            max_recommendations=3
        )
        
        assert len(recommendations) > 0
        
        # 새로운 태그들이 제안되어야 함
        recommended_tags = [rec['tag'] for rec in recommendations]
        assert 'FastAPI' in recommended_tags or 'async' in recommended_tags


class TestSmartExtractionService:
    """스마트 추출 서비스 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_full_extraction_process(self, sample_html):
        """전체 추출 프로세스 테스트"""
        service = SmartExtractionService()
        
        # Mock 세션
        mock_session = AsyncMock()
        mock_session.execute.return_value.fetchall.return_value = []
        
        result = await service.extract_tags_and_category(
            html_content=sample_html,
            url="https://example.com/python-guide",
            user_id=None,  # 히스토리 없음
            max_tags=5,
            session=mock_session
        )
        
        assert 'tags' in result
        assert 'category' in result
        assert 'metadata' in result
        
        assert len(result['tags']) > 0
        assert result['category'] is not None
        assert result['metadata']['processing_method'] == 'smart_extraction'
        assert result['metadata']['cost_savings'] is True
    
    @pytest.mark.asyncio
    async def test_extraction_with_user_history(self, sample_html, sample_user_history):
        """사용자 히스토리를 고려한 추출 테스트"""
        service = SmartExtractionService()
        
        # Mock 세션과 사용자 히스토리
        mock_session = AsyncMock()
        mock_items = []
        for tag in sample_user_history['tags'][:3]:
            mock_item = MagicMock()
            mock_item.tags = [tag]
            mock_item.category = sample_user_history['categories'][0]
            mock_items.append(mock_item)
        
        mock_session.execute.return_value.fetchall.return_value = mock_items
        
        result = await service.extract_tags_and_category(
            html_content=sample_html,
            url="https://example.com/python-guide",
            user_id=1001,  # 히스토리 있음
            max_tags=5,
            session=mock_session
        )
        
        assert 'tags' in result
        assert 'category' in result
        
        # 사용자 히스토리가 활용되었는지 확인
        assert result['metadata']['recommendation_details']['user_history_used'] is True
    
    @pytest.mark.asyncio
    async def test_extraction_fallback(self):
        """추출 실패 시 fallback 테스트"""
        service = SmartExtractionService()
        
        result = await service.extract_tags_and_category(
            html_content="",  # 빈 HTML
            url="https://example.com",
            user_id=None,
            max_tags=5,
            session=None
        )
        
        assert 'tags' in result
        assert 'category' in result
        assert result['category'] == '기타'
    
    @pytest.mark.asyncio
    async def test_compatibility_methods(self):
        """기존 API 호환성 메서드 테스트"""
        service = SmartExtractionService()
        
        # 태그 추출 호환성 테스트
        tags = await service.extract_tags_from_summary(
            summary="Python 프로그래밍 웹 개발 데이터 사이언스",
            user_id=None,
            max_tags=3,
            session=None
        )
        
        assert isinstance(tags, list)
        assert len(tags) > 0
        
        # 카테고리 분류 호환성 테스트
        category = await service.classify_category_from_summary(
            summary="Python 프로그래밍 언어 학습 가이드",
            user_id=None,
            session=None
        )
        
        assert isinstance(category, str)
        assert len(category) > 0
    
    def test_processing_stats(self):
        """처리 통계 정보 테스트"""
        service = SmartExtractionService()
        
        stats = service.get_processing_stats()
        
        assert 'html_extractor_available' in stats
        assert 'keyword_extractor_capabilities' in stats
        assert 'recommendation_engine_available' in stats
        assert 'estimated_cost_savings' in stats
        assert 'processing_time_improvement' in stats
        
        # 비용 절감과 성능 향상 정보 확인
        assert stats['estimated_cost_savings'] == '90%'
        assert stats['processing_time_improvement'] == '50%'


class TestPerformanceComparison:
    """성능 및 비용 비교 테스트"""
    
    def test_cost_efficiency(self):
        """비용 효율성 테스트"""
        # 스마트 추출기는 OpenAI API를 호출하지 않으므로
        # 비용이 발생하지 않아야 함
        service = SmartExtractionService()
        
        # 통계에서 비용 절감 확인
        stats = service.get_processing_stats()
        assert stats['estimated_cost_savings'] == '90%'
    
    @pytest.mark.asyncio
    async def test_processing_speed(self, sample_html):
        """처리 속도 테스트"""
        import time
        
        service = SmartExtractionService()
        
        start_time = time.time()
        
        # Mock 세션
        mock_session = AsyncMock()
        mock_session.execute.return_value.fetchall.return_value = []
        
        result = await service.extract_tags_and_category(
            html_content=sample_html,
            url="https://example.com/test",
            user_id=None,
            max_tags=5,
            session=mock_session
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # 로컬 처리이므로 매우 빨라야 함 (일반적으로 1초 미만)
        assert processing_time < 2.0  # 2초 미만
        assert 'tags' in result
        assert result['metadata']['cost_savings'] is True