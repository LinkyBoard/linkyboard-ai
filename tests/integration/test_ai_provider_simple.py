"""
AI Provider 간단한 통합 테스트
OpenAI Provider와 AI Router의 기본 통합만 검증
"""

import pytest
from unittest.mock import AsyncMock, patch, Mock
from uuid import uuid4

from app.ai.providers.router import AIModelRouter
from app.ai.providers.interface import AIResponse
from app.core.models import ModelCatalog


@pytest.fixture
def simple_mock_model_catalog():
    """간단한 모델 카탈로그 Mock"""
    catalog = Mock(spec=ModelCatalog)
    catalog.model_name = "gpt-3.5-turbo"
    catalog.provider = "openai"
    catalog.input_token_weight = 1.0
    catalog.output_token_weight = 4.0
    return catalog


@pytest.fixture 
def simple_mock_openai_response():
    """간단한 OpenAI API 응답 Mock"""
    mock_response = Mock()
    mock_choice = Mock()
    mock_choice.message.content = "Simple test response"
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 15
    mock_response.usage.total_tokens = 25
    mock_response.model = "gpt-3.5-turbo"
    return mock_response


class TestSimpleAIProviderIntegration:
    """간단한 AI Provider 통합 테스트"""

    @pytest.mark.asyncio
    async def test_basic_chat_completion(self, simple_mock_model_catalog, simple_mock_openai_response):
        """
        Given: AI Router와 OpenAI Provider가 설정되어 있음
        When: 기본 채팅 완성을 요청함  
        Then: 성공적인 응답을 받음
        """
        # Given
        with patch('app.ai.providers.router.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.CLAUDE_API_KEY = None
            mock_settings.GOOGLE_API_KEY = None
            
            # AI Router 초기화
            router = AIModelRouter()
            
            # Model catalog service 패치
            router._model_catalog_service.get_model_catalog = AsyncMock(return_value=simple_mock_model_catalog)
            
            # Usage recording 패치
            with patch('app.metrics.record_llm_usage') as mock_record:
                mock_record.return_value = AsyncMock()
                
                # OpenAI Provider Mock 설정
                with patch.object(router._providers['openai'], 'client') as mock_client:
                    mock_client.chat.completions.create = AsyncMock(return_value=simple_mock_openai_response)
                    
                    # When
                    result = await router.generate_chat_completion(
                        messages=[{"role": "user", "content": "Hello"}],
                        model="gpt-3.5-turbo",
                        user_id=1001
                    )
                    
                    # Then
                    assert isinstance(result, AIResponse)
                    assert result.content == "Simple test response"
                    assert result.provider == "openai"
                    assert result.input_tokens > 0
                    assert result.output_tokens > 0

    def test_provider_availability(self):
        """
        Given: 시스템이 설정되어 있음
        When: Provider 가용성을 확인함
        Then: OpenAI만 사용 가능함을 확인함
        """
        # Given & When
        with patch('app.ai.providers.router.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.CLAUDE_API_KEY = None
            mock_settings.GOOGLE_API_KEY = None
            
            router = AIModelRouter()
            available_providers = router.get_available_providers()
            
            # Then
            assert "openai" in available_providers
            # Claude와 Google은 API 키가 없으므로 사용 불가