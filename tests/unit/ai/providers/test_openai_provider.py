"""
OpenAI Provider 단위 테스트
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.ai.providers.openai_provider import OpenAIProvider
from app.ai.providers.interface import AIResponse


@pytest.fixture
def openai_provider():
    """OpenAI Provider 인스턴스"""
    with patch('openai.AsyncOpenAI'):
        provider = OpenAIProvider(api_key="test-key")
        return provider


@pytest.mark.asyncio
async def test_generate_chat_completion_success(openai_provider):
    """채팅 완성 생성 성공 테스트"""
    
    # Mock OpenAI response
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "Test response from OpenAI"
    
    openai_provider.client.chat.completions.create = AsyncMock(return_value=mock_response)
    openai_provider.count_tokens = Mock(side_effect=[100, 50])  # input, output tokens
    
    messages = [{"role": "user", "content": "Test message"}]
    
    result = await openai_provider.generate_chat_completion(
        messages=messages,
        model="gpt-4o-mini",
        max_tokens=1000,
        temperature=0.7
    )
    
    assert isinstance(result, AIResponse)
    assert result.content == "Test response from OpenAI"
    assert result.input_tokens == 100
    assert result.output_tokens == 50
    assert result.model_used == "gpt-4o-mini"
    assert result.provider == "openai"
    
    openai_provider.client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_generate_webpage_tags_success(openai_provider):
    """웹페이지 태그 생성 성공 테스트"""
    
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "python, programming, tutorial, web, development"
    
    openai_provider.client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    result = await openai_provider.generate_webpage_tags(
        summary="Python web development tutorial",
        similar_tags=["python", "web"],
        tag_count=5,
        model="gpt-4o-mini"
    )
    
    assert isinstance(result, list)
    assert len(result) == 5
    assert "python" in result
    assert "programming" in result
    
    openai_provider.client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_recommend_webpage_category_success(openai_provider):
    """웹페이지 카테고리 추천 성공 테스트"""
    
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "Technology"
    
    openai_provider.client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    result = await openai_provider.recommend_webpage_category(
        summary="Latest AI technology trends",
        similar_categories=["Tech", "AI"],
        model="gpt-4o-mini"
    )
    
    assert result == "Technology"
    openai_provider.client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_generate_webpage_summary_success(openai_provider):
    """웹페이지 요약 생성 성공 테스트"""
    
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "This is a summary of the webpage content."
    
    openai_provider.client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    result = await openai_provider.generate_webpage_summary(
        url="https://example.com",
        html_content="<html>Test content</html>",
        model="gpt-4o-mini"
    )
    
    assert result == "This is a summary of the webpage content."
    openai_provider.client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_generate_youtube_summary_success(openai_provider):
    """YouTube 요약 생성 성공 테스트"""
    
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "YouTube video summary about Python programming."
    
    openai_provider.client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    result = await openai_provider.generate_youtube_summary(
        title="Python Tutorial for Beginners",
        transcript="This video covers Python basics...",
        model="gpt-4o-mini"
    )
    
    assert result == "YouTube video summary about Python programming."
    openai_provider.client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_generate_youtube_tags_success(openai_provider):
    """YouTube 태그 생성 성공 테스트"""
    
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "python, tutorial, programming, beginner, coding"
    
    openai_provider.client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    result = await openai_provider.generate_youtube_tags(
        title="Python Tutorial for Beginners",
        summary="A comprehensive Python tutorial",
        tag_count=5,
        model="gpt-4o-mini"
    )
    
    assert isinstance(result, list)
    assert len(result) == 5
    assert "python" in result
    assert "tutorial" in result


@pytest.mark.asyncio
async def test_recommend_youtube_category_success(openai_provider):
    """YouTube 카테고리 추천 성공 테스트"""
    
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "Education"
    
    openai_provider.client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    result = await openai_provider.recommend_youtube_category(
        title="Python Tutorial for Beginners",
        summary="A comprehensive Python tutorial",
        model="gpt-4o-mini"
    )
    
    assert result == "Education"
    openai_provider.client.chat.completions.create.assert_called_once()


def test_count_tokens(openai_provider):
    """토큰 계산 테스트"""
    with patch('app.ai.providers.openai_provider.count_tokens', return_value=42):
        result = openai_provider.count_tokens("test text", "gpt-4o-mini")
        assert result == 42


def test_provider_name(openai_provider):
    """Provider 이름 테스트"""
    assert openai_provider._get_provider_name() == "openai"
    assert openai_provider.provider_name == "openai"


def test_is_available(openai_provider):
    """사용 가능 여부 테스트"""
    assert openai_provider.is_available() is True
    
    # API 키가 없는 경우
    no_key_provider = OpenAIProvider("")
    assert no_key_provider.is_available() is False


@pytest.mark.asyncio
async def test_api_error_handling(openai_provider):
    """API 오류 처리 테스트"""
    
    openai_provider.client.chat.completions.create = AsyncMock(
        side_effect=Exception("OpenAI API Error")
    )
    
    with pytest.raises(Exception, match="OpenAI API 호출 중 오류"):
        await openai_provider.generate_chat_completion(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4o-mini"
        )