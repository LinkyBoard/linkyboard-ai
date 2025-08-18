"""
Claude Provider 단위 테스트
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.ai.providers.claude_provider import ClaudeProvider
from app.ai.providers.interface import AIResponse


@pytest.fixture
def claude_provider_available():
    """사용 가능한 Claude Provider"""
    with patch('app.ai.providers.claude_provider.anthropic') as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        
        provider = ClaudeProvider(api_key="test-key")
        provider._anthropic_available = True
        provider.client = mock_client
        return provider


@pytest.fixture 
def claude_provider_unavailable():
    """사용 불가능한 Claude Provider (패키지 미설치)"""
    provider = ClaudeProvider(api_key="test-key")
    provider._anthropic_available = False
    provider.client = None
    return provider


@pytest.mark.asyncio
async def test_generate_chat_completion_success(claude_provider_available):
    """채팅 완성 생성 성공 테스트"""
    
    # Mock Claude response
    mock_response = Mock()
    mock_response.content = [Mock()]
    mock_response.content[0].text = "Test response from Claude"
    
    claude_provider_available.client.messages.create = AsyncMock(return_value=mock_response)
    claude_provider_available.count_tokens = Mock(side_effect=[100, 50])
    
    messages = [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Test message"}
    ]
    
    result = await claude_provider_available.generate_chat_completion(
        messages=messages,
        model="claude-3-haiku-20240307",
        max_tokens=1000,
        temperature=0.7
    )
    
    assert isinstance(result, AIResponse)
    assert result.content == "Test response from Claude"
    assert result.input_tokens == 100
    assert result.output_tokens == 50
    assert result.model_used == "claude-3-haiku-20240307"
    assert result.provider == "claude"


@pytest.mark.asyncio
async def test_generate_webpage_tags_success(claude_provider_available):
    """웹페이지 태그 생성 성공 테스트"""
    
    mock_response = Mock()
    mock_response.content = [Mock()]
    mock_response.content[0].text = "python, programming, tutorial, web, development"
    
    claude_provider_available.client.messages.create = AsyncMock(return_value=mock_response)
    
    result = await claude_provider_available.generate_webpage_tags(
        summary="Python web development tutorial",
        similar_tags=["python", "web"],
        tag_count=5,
        model="claude-3-haiku-20240307"
    )
    
    assert isinstance(result, list)
    assert len(result) == 5
    assert "python" in result
    assert "programming" in result


@pytest.mark.asyncio
async def test_recommend_webpage_category_success(claude_provider_available):
    """웹페이지 카테고리 추천 성공 테스트"""
    
    mock_response = Mock()
    mock_response.content = [Mock()]
    mock_response.content[0].text = "Technology"
    
    claude_provider_available.client.messages.create = AsyncMock(return_value=mock_response)
    
    result = await claude_provider_available.recommend_webpage_category(
        summary="Latest AI technology trends",
        similar_categories=["Tech", "AI"],
        model="claude-3-haiku-20240307"
    )
    
    assert result == "Technology"


@pytest.mark.asyncio
async def test_generate_youtube_summary_success(claude_provider_available):
    """YouTube 요약 생성 성공 테스트"""
    
    mock_response = Mock()
    mock_response.content = [Mock()]
    mock_response.content[0].text = "YouTube video summary about Python programming."
    
    claude_provider_available.client.messages.create = AsyncMock(return_value=mock_response)
    
    result = await claude_provider_available.generate_youtube_summary(
        title="Python Tutorial for Beginners",
        transcript="This video covers Python basics...",
        model="claude-3-haiku-20240307"
    )
    
    assert result == "YouTube video summary about Python programming."


def test_provider_name(claude_provider_available):
    """Provider 이름 테스트"""
    assert claude_provider_available._get_provider_name() == "claude"
    assert claude_provider_available.provider_name == "claude"


def test_is_available_true(claude_provider_available):
    """사용 가능한 경우 테스트"""
    assert claude_provider_available.is_available() is True


def test_is_available_false(claude_provider_unavailable):
    """사용 불가능한 경우 테스트"""
    assert claude_provider_unavailable.is_available() is False


@pytest.mark.asyncio
async def test_unavailable_provider_error(claude_provider_unavailable):
    """사용 불가능한 Provider 오류 테스트"""
    
    with pytest.raises(Exception, match="Claude provider is not available"):
        await claude_provider_unavailable.generate_chat_completion(
            messages=[{"role": "user", "content": "test"}],
            model="claude-3-haiku-20240307"
        )


def test_count_tokens(claude_provider_available):
    """토큰 계산 테스트"""
    with patch('tiktoken.get_encoding') as mock_encoding:
        mock_enc = Mock()
        mock_enc.encode.return_value = [1, 2, 3, 4]  # 4 tokens
        mock_encoding.return_value = mock_enc
        
        result = claude_provider_available.count_tokens("test text", "claude-3-haiku-20240307")
        assert result == 4


def test_count_tokens_fallback(claude_provider_available):
    """토큰 계산 폴백 테스트"""
    with patch('tiktoken.get_encoding', side_effect=Exception("Error")):
        result = claude_provider_available.count_tokens("test", "claude-3-haiku-20240307")
        # 4 characters / 4 = 1 token
        assert result == 1


@pytest.mark.asyncio
async def test_api_error_handling(claude_provider_available):
    """API 오류 처리 테스트"""
    
    claude_provider_available.client.messages.create = AsyncMock(
        side_effect=Exception("Claude API Error")
    )
    
    with pytest.raises(Exception, match="Claude API 호출 중 오류"):
        await claude_provider_available.generate_chat_completion(
            messages=[{"role": "user", "content": "test"}],
            model="claude-3-haiku-20240307"
        )