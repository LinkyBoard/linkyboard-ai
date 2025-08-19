"""
AI Router Unit Tests (BDD Style)

AI Router의 단위 테스트를 Given-When-Then 형식으로 작성
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.ai.providers.router import AIModelRouter
from app.ai.providers.interface import AIResponse, TokenUsage
from app.core.models import ModelCatalog


class TestAIRouterUnit:
    """AI Router 단위 테스트 (Given-When-Then)"""

    @pytest.fixture
    def mock_model_catalog(self):
        """Given: 모델 카탈로그가 준비되어 있음"""
        catalog = Mock(spec=ModelCatalog)
        catalog.model_name = "gpt-4o-mini"
        catalog.alias = "GPT-4o Mini"
        catalog.provider = "openai"
        catalog.weight_input = 0.6
        catalog.weight_output = 2.4
        return catalog

    @pytest.fixture
    def ai_router(self):
        """Given: AI Router가 초기화되어 있음"""
        with patch('app.ai.providers.router.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.CLAUDE_API_KEY = None
            mock_settings.GOOGLE_API_KEY = None
            router = AIModelRouter()
            return router

    @pytest.mark.asyncio
    async def test_given_valid_model_when_get_provider_then_returns_provider(
        self, ai_router, mock_model_catalog
    ):
        """
        Given: 유효한 모델이 카탈로그에 있음
        When: 모델에 대한 Provider를 조회함
        Then: 적절한 Provider를 반환함
        """
        # Given
        model_name = "gpt-4o-mini"
        
        # When
        with patch.object(ai_router._model_catalog_service, 'get_model_catalog', return_value=mock_model_catalog):
            provider, catalog = await ai_router.get_provider_for_model(model_name)
        
        # Then
        assert provider is not None
        assert provider.provider_name == "openai"
        assert catalog == mock_model_catalog

    @pytest.mark.asyncio
    async def test_given_invalid_model_when_get_provider_then_raises_error(self, ai_router):
        """
        Given: 존재하지 않는 모델이 지정됨
        When: 모델에 대한 Provider를 조회함
        Then: ValueError가 발생함
        """
        # Given
        invalid_model = "unknown-model"
        
        # When & Then
        with patch.object(ai_router._model_catalog_service, 'get_model_catalog', return_value=None):
            with pytest.raises(ValueError, match="Model 'unknown-model' not found in catalog"):
                await ai_router.get_provider_for_model(invalid_model)

    @pytest.mark.asyncio
    async def test_given_valid_messages_when_generate_chat_completion_then_returns_response(
        self, ai_router, mock_model_catalog
    ):
        """
        Given: 유효한 메시지와 모델이 제공됨
        When: 채팅 완성을 생성함
        Then: AI 응답을 반환함
        """
        # Given
        messages = [{"role": "user", "content": "Test message"}]
        model = "gpt-4o-mini"
        user_id = 123
        
        mock_response = AIResponse(
            content="Test response",
            input_tokens=100,
            output_tokens=50,
            model_used="gpt-4o-mini",
            provider="openai"
        )
        
        # When
        with patch.object(ai_router, 'get_provider_for_model') as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.generate_chat_completion.return_value = mock_response
            mock_get_provider.return_value = (mock_provider, mock_model_catalog)
            
            with patch.object(ai_router, '_record_usage') as mock_record:
                result = await ai_router.generate_chat_completion(
                    messages=messages,
                    model=model,
                    user_id=user_id
                )
        
        # Then
        assert result == mock_response
        mock_provider.generate_chat_completion.assert_called_once()
        mock_record.assert_called_once()

    @pytest.mark.asyncio 
    async def test_given_model_type_when_get_available_models_then_returns_model_list(self, ai_router):
        """
        Given: 특정 모델 타입이 지정됨
        When: 사용 가능한 모델 목록을 조회함
        Then: 해당 타입의 모델 목록을 반환함
        """
        # Given
        model_type = "llm"
        mock_models = [
            Mock(
                model_name="gpt-4o-mini",
                alias="GPT-4o Mini", 
                provider="openai",
                model_type="llm",
                weight_input=0.6,
                weight_output=2.4
            )
        ]
        
        # When
        with patch.object(ai_router._model_catalog_service, 'get_active_models', return_value=mock_models):
            result = await ai_router.get_available_models(model_type)
        
        # Then
        assert len(result) == 1
        assert result[0]["model_name"] == "gpt-4o-mini"
        assert result[0]["provider"] == "openai"
        assert result[0]["input_cost_per_1k"] == 600  # 0.6 * 1000

    def test_given_router_initialized_when_get_available_providers_then_returns_provider_list(self, ai_router):
        """
        Given: AI Router가 초기화되어 있음
        When: 사용 가능한 Provider 목록을 조회함
        Then: 활성화된 Provider 목록을 반환함
        """
        # Given & When
        providers = ai_router.get_available_providers()
        
        # Then
        assert "openai" in providers
        # Claude와 Google은 API 키가 없으므로 포함되지 않음

    @pytest.mark.asyncio
    async def test_given_webpage_content_when_generate_tags_then_returns_tag_list(
        self, ai_router, mock_model_catalog
    ):
        """
        Given: 웹페이지 컨텐츠가 제공됨
        When: 태그 생성을 요청함
        Then: 태그 목록을 반환함
        """
        # Given
        summary = "Python tutorial content"
        model = "gpt-4o-mini"
        user_id = 123
        mock_tags = ["python", "programming", "tutorial"]
        
        # When
        with patch.object(ai_router, 'get_provider_for_model') as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.generate_webpage_tags.return_value = mock_tags
            mock_provider.count_tokens.return_value = 50
            mock_get_provider.return_value = (mock_provider, mock_model_catalog)
            
            with patch.object(ai_router, '_record_usage'):
                result = await ai_router.generate_webpage_tags(
                    summary=summary,
                    model=model,
                    user_id=user_id
                )
        
        # Then
        assert result == mock_tags
        mock_provider.generate_webpage_tags.assert_called_once()

    @pytest.mark.asyncio
    async def test_given_webpage_content_when_recommend_category_then_returns_category(
        self, ai_router, mock_model_catalog
    ):
        """
        Given: 웹페이지 컨텐츠가 제공됨
        When: 카테고리 추천을 요청함
        Then: 카테고리를 반환함
        """
        # Given
        summary = "Technology article"
        model = "gpt-4o-mini"
        user_id = 123
        mock_category = "Technology"
        
        # When
        with patch.object(ai_router, 'get_provider_for_model') as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.recommend_webpage_category.return_value = mock_category
            mock_provider.count_tokens.return_value = 30
            mock_get_provider.return_value = (mock_provider, mock_model_catalog)
            
            with patch.object(ai_router, '_record_usage'):
                result = await ai_router.recommend_webpage_category(
                    summary=summary,
                    model=model,
                    user_id=user_id
                )
        
        # Then
        assert result == mock_category
        mock_provider.recommend_webpage_category.assert_called_once()

    @pytest.mark.asyncio
    async def test_given_usage_data_when_record_usage_then_records_successfully(
        self, ai_router, mock_model_catalog
    ):
        """
        Given: 사용량 데이터가 제공됨
        When: 사용량을 기록함
        Then: 성공적으로 기록됨
        """
        # Given
        user_id = 123
        input_tokens = 50
        output_tokens = 25
        
        # When
        with patch('app.ai.providers.router.record_llm_usage') as mock_record_llm:
            with patch('app.ai.providers.router.calculate_wtu', return_value=(100, 0.5)) as mock_calc_wtu:
                with patch('app.ai.providers.router.record_wtu_usage') as mock_record_wtu:
                    
                    await ai_router._record_usage(
                        user_id=user_id,
                        model_catalog=mock_model_catalog,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens
                    )
        
        # Then
        mock_record_llm.assert_called_once_with(
            user_id=user_id,
            in_tokens=input_tokens,
            out_tokens=output_tokens,
            llm_model="gpt-4o-mini",
            board_id=None,
            session=None
        )
        mock_calc_wtu.assert_called_once()
        mock_record_wtu.assert_called_once()

    @pytest.mark.asyncio
    async def test_given_multiple_models_when_get_default_model_then_returns_cheapest(self, ai_router):
        """
        Given: 여러 모델이 활성화되어 있음
        When: 기본 모델을 조회함
        Then: 가장 저렴한 모델을 반환함
        """
        # Given
        mock_models = [
            Mock(weight_input=0.3, weight_output=0.6, model_name="gemini-1.5-flash"),  # 가장 저렴
            Mock(weight_input=0.6, weight_output=2.4, model_name="gpt-4o-mini"),      # 중간
            Mock(weight_input=1.0, weight_output=2.5, model_name="claude-3-haiku")    # 비쌈
        ]
        
        # When
        with patch.object(ai_router._model_catalog_service, 'get_active_models', return_value=mock_models):
            default_model = await ai_router._get_default_model("llm")
        
        # Then
        assert default_model == "gemini-1.5-flash"