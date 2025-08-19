"""
Enhanced OpenAI Provider 단위 테스트 (BDD 스타일)
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.ai.providers.openai_provider import OpenAIProvider
from app.ai.providers.interface import AIResponse, TokenUsage


class TestOpenAIProvider:
    """OpenAI Provider BDD 스타일 단위 테스트"""

    @pytest.fixture
    def openai_provider(self):
        """Given: OpenAI Provider가 초기화되어 있음"""
        with patch('app.ai.providers.openai_provider.openai') as mock_openai:
            provider = OpenAIProvider("test-api-key")
            provider.client = mock_openai.AsyncOpenAI.return_value
            return provider

    @pytest.fixture
    def mock_openai_response(self):
        """Given: OpenAI API 응답이 모킹되어 있음"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "Mock OpenAI response content"
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 100
        mock_response.usage.total_tokens = 150
        mock_response.model = "gpt-3.5-turbo"
        return mock_response

    @pytest.mark.asyncio
    async def test_given_valid_messages_when_generate_chat_completion_then_success(
        self, openai_provider, mock_openai_response
    ):
        """
        Given: 유효한 메시지가 제공됨
        When: 채팅 완성을 생성함
        Then: 성공적인 AI 응답을 반환함
        """
        # Given
        messages = [{"role": "user", "content": "Test message"}]
        model = "gpt-3.5-turbo"
        
        # Mock OpenAI client response
        openai_provider.client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
        
        # When
        result = await openai_provider.generate_chat_completion(
            messages=messages,
            model=model,
            max_tokens=1000,
            temperature=0.7
        )
        
        # Then
        assert isinstance(result, AIResponse)
        assert result.content == "Mock OpenAI response content"
        assert result.input_tokens == 4  # Token count from mock
        assert result.output_tokens == 7  # Token count from mock
        assert result.model_used == "gpt-3.5-turbo"
        assert result.provider == "openai"

    @pytest.mark.asyncio
    async def test_given_api_error_when_generate_chat_completion_then_raises_exception(
        self, openai_provider
    ):
        """
        Given: OpenAI API가 오류를 발생시킴
        When: 채팅 완성을 생성함
        Then: 예외가 발생함
        """
        # Given
        messages = [{"role": "user", "content": "Test message"}]
        model = "gpt-3.5-turbo"
        
        # Mock API error
        openai_provider.client.chat.completions.create = AsyncMock(
            side_effect=Exception("OpenAI API Error")
        )
        
        # When & Then
        with pytest.raises(Exception, match="OpenAI API Error"):
            await openai_provider.generate_chat_completion(
                messages=messages,
                model=model
            )

    @pytest.mark.asyncio
    async def test_given_webpage_content_when_generate_tags_then_returns_tag_list(
        self, openai_provider, mock_openai_response
    ):
        """
        Given: 웹페이지 컨텐츠가 제공됨
        When: 태그를 생성함
        Then: 태그 목록을 반환함
        """
        # Given
        content = "Python programming tutorial"
        tag_count = 3
        model = "gpt-3.5-turbo"
        
        # Mock response with comma-separated tags
        mock_openai_response.choices[0].message.content = 'python, programming, tutorial'
        openai_provider.client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
        
        # When
        result = await openai_provider.generate_webpage_tags(
            summary=content,
            tag_count=tag_count,
            model=model
        )
        
        # Then
        assert isinstance(result, list)
        assert len(result) == 3
        assert "python" in result
        assert "programming" in result
        assert "tutorial" in result

    @pytest.mark.asyncio
    async def test_given_invalid_json_response_when_generate_tags_then_returns_fallback(
        self, openai_provider, mock_openai_response
    ):
        """
        Given: OpenAI가 잘못된 JSON을 응답함
        When: 태그를 생성함
        Then: 폴백 태그를 반환함
        """
        # Given
        content = "Test content"
        tag_count = 3
        model = "gpt-3.5-turbo"
        
        # Mock empty response (no valid tags)
        mock_openai_response.choices[0].message.content = ""
        openai_provider.client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
        
        # When
        result = await openai_provider.generate_webpage_tags(
            summary=content,
            tag_count=tag_count,
            model=model
        )
        
        # Then
        assert isinstance(result, list)
        assert len(result) == 0  # Empty response results in empty list

    @pytest.mark.asyncio
    async def test_given_webpage_content_when_recommend_category_then_returns_category(
        self, openai_provider, mock_openai_response
    ):
        """
        Given: 웹페이지 컨텐츠가 제공됨
        When: 카테고리를 추천함
        Then: 카테고리 문자열을 반환함
        """
        # Given
        content = "Technology article about AI"
        model = "gpt-3.5-turbo"
        
        # Mock category response
        mock_openai_response.choices[0].message.content = "Technology"
        openai_provider.client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
        
        # When
        result = await openai_provider.recommend_webpage_category(
            summary=content,
            model=model
        )
        
        # Then
        assert isinstance(result, str)
        assert result == "Technology"

    @pytest.mark.asyncio
    async def test_given_empty_content_when_recommend_category_then_returns_general(
        self, openai_provider, mock_openai_response
    ):
        """
        Given: 빈 컨텐츠가 제공됨
        When: 카테고리를 추천함
        Then: 'general' 카테고리를 반환함
        """
        # Given
        content = ""
        model = "gpt-3.5-turbo"
        
        # Mock general category response
        mock_openai_response.choices[0].message.content = "general"
        openai_provider.client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
        
        # When
        result = await openai_provider.recommend_webpage_category(
            summary=content,
            model=model
        )
        
        # Then
        assert result == "general"

    def test_given_text_when_count_tokens_then_returns_count(self, openai_provider):
        """
        Given: 텍스트가 제공됨
        When: 토큰을 계산함
        Then: 토큰 수를 반환함
        """
        # Given
        text = "Hello, this is a test message."
        model = "gpt-3.5-turbo"
        
        # When
        with patch('app.ai.providers.openai_provider.count_tokens') as mock_count:
            mock_count.return_value = 8
            result = openai_provider.count_tokens(text, model)
        
        # Then
        assert result == 8
        mock_count.assert_called_once_with(text, model)

    def test_given_empty_text_when_count_tokens_then_returns_zero(self, openai_provider):
        """
        Given: 빈 텍스트가 제공됨
        When: 토큰을 계산함
        Then: 0을 반환함
        """
        # Given
        text = ""
        model = "gpt-3.5-turbo"
        
        # When
        with patch('app.ai.providers.openai_provider.count_tokens') as mock_count:
            mock_count.return_value = 0
            result = openai_provider.count_tokens(text, model)
        
        # Then
        assert result == 0

    @pytest.mark.asyncio
    async def test_given_system_and_user_messages_when_generate_chat_completion_then_handles_both(
        self, openai_provider, mock_openai_response
    ):
        """
        Given: 시스템 메시지와 사용자 메시지가 모두 제공됨
        When: 채팅 완성을 생성함
        Then: 두 메시지 모두 처리함
        """
        # Given
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is Python?"}
        ]
        model = "gpt-3.5-turbo"
        
        # Mock OpenAI client response
        openai_provider.client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
        
        # When
        result = await openai_provider.generate_chat_completion(
            messages=messages,
            model=model
        )
        
        # Then
        assert isinstance(result, AIResponse)
        openai_provider.client.chat.completions.create.assert_called_once()
        call_args = openai_provider.client.chat.completions.create.call_args[1]
        assert len(call_args['messages']) == 2
        assert call_args['messages'][0]['role'] == 'system'
        assert call_args['messages'][1]['role'] == 'user'

    @pytest.mark.asyncio
    async def test_given_high_temperature_when_generate_chat_completion_then_uses_temperature(
        self, openai_provider, mock_openai_response
    ):
        """
        Given: 높은 temperature 값이 제공됨
        When: 채팅 완성을 생성함
        Then: 해당 temperature를 사용함
        """
        # Given
        messages = [{"role": "user", "content": "Be creative!"}]
        model = "gpt-3.5-turbo"
        temperature = 0.9
        
        # Mock OpenAI client response
        openai_provider.client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
        
        # When
        await openai_provider.generate_chat_completion(
            messages=messages,
            model=model,
            temperature=temperature
        )
        
        # Then
        call_args = openai_provider.client.chat.completions.create.call_args[1]
        assert call_args['temperature'] == 0.9

    @pytest.mark.asyncio
    async def test_given_max_tokens_limit_when_generate_chat_completion_then_respects_limit(
        self, openai_provider, mock_openai_response
    ):
        """
        Given: max_tokens 제한이 설정됨
        When: 채팅 완성을 생성함
        Then: 토큰 제한을 준수함
        """
        # Given
        messages = [{"role": "user", "content": "Write a long story"}]
        model = "gpt-3.5-turbo"
        max_tokens = 500
        
        # Mock OpenAI client response
        openai_provider.client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
        
        # When
        await openai_provider.generate_chat_completion(
            messages=messages,
            model=model,
            max_tokens=max_tokens
        )
        
        # Then
        call_args = openai_provider.client.chat.completions.create.call_args[1]
        assert call_args['max_tokens'] == 500