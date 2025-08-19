"""
Google Provider 단위 테스트
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.ai.providers.google_provider import GoogleProvider
from app.ai.providers.interface import AIResponse


@pytest.fixture
def google_provider_available():
    """사용 가능한 Google Provider"""
    with patch('google.generativeai') as mock_genai:
        mock_model = AsyncMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.configure = Mock()
        mock_genai.types.GenerationConfig = Mock()
        
        provider = GoogleProvider(api_key="test-key")
        provider._google_available = True
        provider._genai = mock_genai
        return provider


@pytest.fixture 
def google_provider_unavailable():
    """사용 불가능한 Google Provider (패키지 미설치)"""
    provider = GoogleProvider(api_key="test-key")
    provider._google_available = False
    provider._genai = None
    return provider


@pytest.mark.asyncio
async def test_generate_chat_completion_success(google_provider_available):
    """채팅 완성 생성 성공 테스트"""
    
    # Mock Google response
    mock_response = Mock()
    mock_response.text = "Test response from Google"
    
    mock_model = google_provider_available._genai.GenerativeModel.return_value
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)
    
    google_provider_available.count_tokens = Mock(side_effect=[100, 50])
    
    messages = [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Test message"}
    ]
    
    result = await google_provider_available.generate_chat_completion(
        messages=messages,
        model="gemini-pro",
        max_tokens=1000,
        temperature=0.7
    )
    
    assert isinstance(result, AIResponse)
    assert result.content == "Test response from Google"
    assert result.input_tokens == 100
    assert result.output_tokens == 50
    assert result.model_used == "gemini-pro"
    assert result.provider == "google"


@pytest.mark.asyncio
async def test_generate_webpage_tags_success(google_provider_available):
    """웹페이지 태그 생성 성공 테스트"""
    
    mock_response = Mock()
    mock_response.text = "python, programming, tutorial, web, development"
    
    mock_model = google_provider_available._genai.GenerativeModel.return_value
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)
    
    result = await google_provider_available.generate_webpage_tags(
        summary="Python web development tutorial",
        similar_tags=["python", "web"],
        tag_count=5,
        model="gemini-pro"
    )
    
    assert isinstance(result, list)
    assert len(result) == 5
    assert "python" in result
    assert "programming" in result


@pytest.mark.asyncio
async def test_recommend_webpage_category_success(google_provider_available):
    """웹페이지 카테고리 추천 성공 테스트"""
    
    mock_response = Mock()
    mock_response.text = "Technology"
    
    mock_model = google_provider_available._genai.GenerativeModel.return_value
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)
    
    result = await google_provider_available.recommend_webpage_category(
        summary="Latest AI technology trends",
        similar_categories=["Tech", "AI"],
        model="gemini-pro"
    )
    
    assert result == "Technology"


@pytest.mark.asyncio
async def test_generate_youtube_summary_success(google_provider_available):
    """YouTube 요약 생성 성공 테스트"""
    
    mock_response = Mock()
    mock_response.text = "YouTube video summary about Python programming."
    
    mock_model = google_provider_available._genai.GenerativeModel.return_value
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)
    
    result = await google_provider_available.generate_youtube_summary(
        title="Python Tutorial for Beginners",
        transcript="This video covers Python basics...",
        model="gemini-pro"
    )
    
    assert result == "YouTube video summary about Python programming."


def test_provider_name(google_provider_available):
    """Provider 이름 테스트"""
    assert google_provider_available._get_provider_name() == "google"
    assert google_provider_available.provider_name == "google"


def test_is_available_true(google_provider_available):
    """사용 가능한 경우 테스트"""
    assert google_provider_available.is_available() is True


def test_is_available_false(google_provider_unavailable):
    """사용 불가능한 경우 테스트"""
    assert google_provider_unavailable.is_available() is False


@pytest.mark.asyncio
async def test_unavailable_provider_error(google_provider_unavailable):
    """사용 불가능한 Provider 오류 테스트"""
    
    with pytest.raises(Exception, match="Google provider is not available"):
        await google_provider_unavailable.generate_chat_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gemini-pro"
        )


def test_count_tokens(google_provider_available):
    """토큰 계산 테스트"""
    with patch('tiktoken.get_encoding') as mock_encoding:
        mock_enc = Mock()
        mock_enc.encode.return_value = [1, 2, 3, 4]  # 4 tokens
        mock_encoding.return_value = mock_enc
        
        result = google_provider_available.count_tokens("test text", "gemini-pro")
        assert result == 4


def test_count_tokens_fallback(google_provider_available):
    """토큰 계산 폴백 테스트"""
    with patch('tiktoken.get_encoding', side_effect=Exception("Error")):
        result = google_provider_available.count_tokens("test", "gemini-pro")
        # 4 characters / 4 = 1 token
        assert result == 1


@pytest.mark.asyncio
async def test_api_error_handling(google_provider_available):
    """API 오류 처리 테스트"""
    
    mock_model = google_provider_available._genai.GenerativeModel.return_value
    mock_model.generate_content_async = AsyncMock(
        side_effect=Exception("Google API Error")
    )
    
    with pytest.raises(Exception, match="Google API 호출 중 오류"):
        await google_provider_available.generate_chat_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gemini-pro"
        )


def test_format_messages_for_gemini(google_provider_available):
    """Gemini 메시지 형식 변환 테스트"""
    messages = [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"}
    ]
    
    result = google_provider_available._format_messages_for_gemini(messages)
    
    assert "Instructions: You are helpful" in result
    assert "User: Hello" in result
    assert "Assistant: Hi there!" in result