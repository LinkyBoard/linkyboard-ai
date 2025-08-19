"""
AI Router 단위 테스트
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.ai.providers.router import AIModelRouter
from app.ai.providers.interface import AIResponse, TokenUsage
from app.core.models import ModelCatalog


@pytest.fixture
def mock_model_catalog():
    """모델 카탈로그 Mock"""
    catalog = Mock(spec=ModelCatalog)
    catalog.model_name = "gpt-4o-mini"
    catalog.alias = "GPT-4o Mini"
    catalog.provider = "openai"
    catalog.weight_input = 0.6
    catalog.weight_output = 2.4
    return catalog


@pytest.fixture
def ai_router():
    """AI Router 인스턴스"""
    with patch('app.ai.providers.router.settings') as mock_settings:
        mock_settings.OPENAI_API_KEY = "test-key"
        mock_settings.CLAUDE_API_KEY = None
        mock_settings.GOOGLE_API_KEY = None
        router = AIModelRouter()
        return router


@pytest.mark.asyncio
async def test_get_provider_for_model_success(ai_router, mock_model_catalog):
    """모델에 대한 Provider 조회 성공 테스트"""
    
    with patch.object(ai_router._model_catalog_service, 'get_model_catalog', return_value=mock_model_catalog):
        provider, catalog = await ai_router.get_provider_for_model("gpt-4o-mini")
        
        assert provider is not None
        assert provider.provider_name == "openai"
        assert catalog == mock_model_catalog


@pytest.mark.asyncio
async def test_get_provider_for_model_not_found(ai_router):
    """존재하지 않는 모델에 대한 테스트"""
    
    with patch.object(ai_router._model_catalog_service, 'get_model_catalog', return_value=None):
        with pytest.raises(ValueError, match="Model 'unknown-model' not found in catalog"):
            await ai_router.get_provider_for_model("unknown-model")


@pytest.mark.asyncio
async def test_generate_chat_completion_success(ai_router, mock_model_catalog):
    """채팅 완성 생성 성공 테스트"""
    
    # Mock AI Response
    mock_response = AIResponse(
        content="Test response",
        input_tokens=100,
        output_tokens=50,
        model_used="gpt-4o-mini",
        provider="openai"
    )
    
    messages = [{"role": "user", "content": "Test message"}]
    
    with patch.object(ai_router, '_get_provider_for_model') as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.generate_chat_completion.return_value = mock_response
        mock_get_provider.return_value = (mock_provider, mock_model_catalog)
        
        with patch.object(ai_router, '_record_usage') as mock_record:
            result = await ai_router.generate_chat_completion(
                messages=messages,
                model="gpt-4o-mini",
                user_id=123
            )
            
            assert result == mock_response
            mock_provider.generate_chat_completion.assert_called_once()
            mock_record.assert_called_once()


@pytest.mark.asyncio 
async def test_get_available_models(ai_router):
    """사용 가능한 모델 목록 조회 테스트"""
    
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
    
    with patch.object(ai_router._model_catalog_service, 'get_active_models', return_value=mock_models):
        result = await ai_router.get_available_models("llm")
        
        assert len(result) == 1
        assert result[0]["model_name"] == "gpt-4o-mini"
        assert result[0]["provider"] == "openai"
        assert result[0]["input_cost_per_1k"] == 600  # 0.6 * 1000


def test_get_available_providers(ai_router):
    """사용 가능한 Provider 목록 테스트"""
    providers = ai_router.get_available_providers()
    assert "openai" in providers
    # Claude와 Google은 API 키가 없으므로 포함되지 않음


@pytest.mark.asyncio
async def test_generate_webpage_tags_success(ai_router, mock_model_catalog):
    """웹페이지 태그 생성 성공 테스트"""
    
    mock_tags = ["python", "programming", "tutorial"]
    
    with patch.object(ai_router, '_get_provider_for_model') as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.generate_webpage_tags.return_value = mock_tags
        mock_provider.count_tokens.return_value = 50
        mock_get_provider.return_value = (mock_provider, mock_model_catalog)
        
        with patch.object(ai_router, '_record_usage'):
            result = await ai_router.generate_webpage_tags(
                summary="Python tutorial content",
                model="gpt-4o-mini",
                user_id=123
            )
            
            assert result == mock_tags
            mock_provider.generate_webpage_tags.assert_called_once()


@pytest.mark.asyncio
async def test_recommend_webpage_category_success(ai_router, mock_model_catalog):
    """웹페이지 카테고리 추천 성공 테스트"""
    
    mock_category = "Technology"
    
    with patch.object(ai_router, '_get_provider_for_model') as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.recommend_webpage_category.return_value = mock_category
        mock_provider.count_tokens.return_value = 30
        mock_get_provider.return_value = (mock_provider, mock_model_catalog)
        
        with patch.object(ai_router, '_record_usage'):
            result = await ai_router.recommend_webpage_category(
                summary="Technology article",
                model="gpt-4o-mini",
                user_id=123
            )
            
            assert result == mock_category
            mock_provider.recommend_webpage_category.assert_called_once()


@pytest.mark.asyncio
async def test_record_usage_success(ai_router, mock_model_catalog):
    """사용량 기록 성공 테스트"""
    
    with patch('app.ai.providers.router.record_llm_usage') as mock_record_llm:
        with patch('app.ai.providers.router.calculate_wtu', return_value=(100, 0.5)) as mock_calc_wtu:
            with patch('app.ai.providers.router.record_wtu_usage') as mock_record_wtu:
                
                await ai_router._record_usage(
                    user_id=123,
                    model_catalog=mock_model_catalog,
                    input_tokens=50,
                    output_tokens=25
                )
                
                mock_record_llm.assert_called_once_with(
                    user_id=123,
                    in_tokens=50,
                    out_tokens=25,
                    llm_model="gpt-4o-mini",
                    board_id=None,
                    session=None
                )
                mock_calc_wtu.assert_called_once()
                mock_record_wtu.assert_called_once()


@pytest.mark.asyncio
async def test_default_model_selection(ai_router):
    """기본 모델 선택 테스트"""
    
    mock_models = [
        Mock(weight_input=0.3, weight_output=0.6, model_name="gemini-1.5-flash"),  # 가장 저렴
        Mock(weight_input=0.6, weight_output=2.4, model_name="gpt-4o-mini"),      # 중간
        Mock(weight_input=1.0, weight_output=2.5, model_name="claude-3-haiku")    # 비쌈
    ]
    
    with patch.object(ai_router._model_catalog_service, 'get_active_models', return_value=mock_models):
        default_model = await ai_router._get_default_model("llm")
        
        # 가장 저렴한 모델이 선택되어야 함
        assert default_model == "gemini-1.5-flash"