"""
AI Provider Interface Functional Tests (BDD Style)

AI 제공자들의 통합 시나리오를 Given-When-Then 형식으로 테스트
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from app.ai.providers.router import AIModelRouter
from app.ai.providers.interface import AIResponse, TokenUsage


class TestAIProviderInterfaceFunctional:
    """AI Provider Interface 기능 테스트 (Given-When-Then)"""

    @pytest.fixture
    def ai_router(self):
        """Given: AI 라우터가 초기화되어 있음"""
        with patch('app.ai.providers.router.AIModelRouter._load_providers'):
            router = AIModelRouter()
            # Mock providers
            router.providers = {
                'openai': Mock()
            }
            return router

    @pytest.fixture
    def test_context(self):
        """Given: 테스트 컨텍스트가 준비되어 있음"""
        return {
            'user_id': 1001,
            'board_id': uuid4(),
            'response': None,
            'error': None
        }

    @pytest.mark.asyncio
    async def test_given_valid_model_when_chat_completion_requested_then_success(
        self, ai_router, test_context
    ):
        """
        Given: 유효한 GPT 모델이 사용 가능함
        When: 사용자가 채팅 완성을 요청함
        Then: 성공적인 AI 응답을 받아야 함
        """
        # Given
        model = "gpt-3.5-turbo"
        messages = [{"role": "user", "content": "안녕하세요, 테스트 메시지입니다"}]
        
        # Mock OpenAI provider response
        mock_response = AIResponse(
            content="안녕하세요! 무엇을 도와드릴까요?",
            token_usage=TokenUsage(input_tokens=10, output_tokens=15, total_tokens=25),
            model="gpt-3.5-turbo",
            provider="openai"
        )
        ai_router.providers['openai'].generate_chat_completion = AsyncMock(return_value=mock_response)
        
        # When
        try:
            test_context['response'] = await ai_router.generate_chat_completion(
                messages=messages,
                model=model,
                user_id=test_context['user_id'],
                board_id=test_context['board_id']
            )
        except Exception as e:
            test_context['error'] = e
        
        # Then
        assert test_context['response'] is not None
        assert test_context['error'] is None
        assert isinstance(test_context['response'], AIResponse)
        assert test_context['response'].content is not None
        assert len(test_context['response'].content) > 0
        assert test_context['response'].token_usage.input_tokens > 0
        assert test_context['response'].token_usage.output_tokens > 0

    @pytest.mark.asyncio
    async def test_given_webpage_content_when_tags_requested_then_returns_valid_tags(
        self, ai_router, test_context
    ):
        """
        Given: 웹페이지 컨텐츠가 제공됨
        When: 사용자가 태그 생성을 요청함
        Then: 유효한 태그 목록을 받아야 함
        """
        # Given
        model = "gpt-3.5-turbo"
        content = "Python 프로그래밍에 대한 기사입니다"
        tag_count = 5
        
        # Mock OpenAI provider response
        mock_tags = ["python", "programming", "tutorial", "development", "coding"]
        ai_router.providers['openai'].generate_webpage_tags = AsyncMock(return_value=mock_tags)
        
        # When
        try:
            test_context['response'] = await ai_router.generate_webpage_tags(
                content=content,
                tag_count=tag_count,
                model=model,
                user_id=test_context['user_id'],
                board_id=test_context['board_id']
            )
        except Exception as e:
            test_context['error'] = e
        
        # Then
        assert test_context['response'] is not None
        assert test_context['error'] is None
        assert isinstance(test_context['response'], list)
        assert len(test_context['response']) == tag_count
        for tag in test_context['response']:
            assert isinstance(tag, str)
            assert len(tag) > 0

    @pytest.mark.asyncio
    async def test_given_webpage_content_when_category_requested_then_returns_valid_category(
        self, ai_router, test_context
    ):
        """
        Given: 웹페이지 컨텐츠가 제공됨
        When: 사용자가 카테고리 추천을 요청함
        Then: 유효한 카테고리를 받아야 함
        """
        # Given
        model = "gpt-3.5-turbo"
        content = "FastAPI를 이용한 REST API 개발 가이드"
        
        # Mock OpenAI provider response
        mock_category = "Technology"
        ai_router.providers['openai'].recommend_webpage_category = AsyncMock(return_value=mock_category)
        
        # When
        try:
            test_context['response'] = await ai_router.recommend_webpage_category(
                content=content,
                model=model,
                user_id=test_context['user_id'],
                board_id=test_context['board_id']
            )
        except Exception as e:
            test_context['error'] = e
        
        # Then
        assert test_context['response'] is not None
        assert test_context['error'] is None
        assert isinstance(test_context['response'], str)
        assert len(test_context['response']) > 0

    @pytest.mark.asyncio
    async def test_given_invalid_model_when_chat_completion_requested_then_error_occurs(
        self, ai_router, test_context
    ):
        """
        Given: 존재하지 않는 모델이 지정됨
        When: 사용자가 채팅 완성을 요청함
        Then: 모델을 찾을 수 없다는 오류가 발생해야 함
        """
        # Given
        invalid_model = "invalid-model"
        messages = [{"role": "user", "content": "테스트 메시지"}]
        
        # When
        try:
            test_context['response'] = await ai_router.generate_chat_completion(
                messages=messages,
                model=invalid_model,
                user_id=test_context['user_id'],
                board_id=test_context['board_id']
            )
        except Exception as e:
            test_context['error'] = e
        
        # Then
        assert test_context['error'] is not None
        assert "model" in str(test_context['error']).lower()

    @pytest.mark.asyncio
    async def test_given_no_model_when_chat_completion_requested_then_default_model_used(
        self, ai_router, test_context
    ):
        """
        Given: 모델이 지정되지 않음
        When: 사용자가 채팅 완성을 요청함
        Then: 기본 모델이 자동으로 선택되어야 함
        """
        # Given
        messages = [{"role": "user", "content": "테스트 메시지"}]
        
        # Mock OpenAI provider response with default model
        mock_response = AIResponse(
            content="기본 모델 응답입니다",
            token_usage=TokenUsage(input_tokens=8, output_tokens=12, total_tokens=20),
            model="gpt-3.5-turbo",  # default model
            provider="openai"
        )
        ai_router.providers['openai'].generate_chat_completion = AsyncMock(return_value=mock_response)
        
        # When
        try:
            test_context['response'] = await ai_router.generate_chat_completion(
                messages=messages,
                model=None,  # No model specified
                user_id=test_context['user_id'],
                board_id=test_context['board_id']
            )
        except Exception as e:
            test_context['error'] = e
        
        # Then
        assert test_context['response'] is not None
        assert test_context['error'] is None
        assert test_context['response'].model is not None
        assert test_context['response'].model == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("model", ["gpt-3.5-turbo", "gpt-4o-mini"])
    async def test_given_different_models_when_chat_completion_requested_then_consistent_format(
        self, ai_router, test_context, model
    ):
        """
        Given: 다양한 모델이 사용 가능함
        When: 사용자가 채팅 완성을 요청함
        Then: 응답 형식이 일관되어야 함
        """
        # Given
        messages = [{"role": "user", "content": "테스트 질문입니다"}]
        
        # Mock OpenAI provider response
        mock_response = AIResponse(
            content=f"{model} 모델 응답입니다",
            token_usage=TokenUsage(input_tokens=10, output_tokens=15, total_tokens=25),
            model=model,
            provider="openai"
        )
        ai_router.providers['openai'].generate_chat_completion = AsyncMock(return_value=mock_response)
        
        # When
        try:
            test_context['response'] = await ai_router.generate_chat_completion(
                messages=messages,
                model=model,
                user_id=test_context['user_id'],
                board_id=test_context['board_id']
            )
        except Exception as e:
            test_context['error'] = e
        
        # Then
        assert test_context['response'] is not None
        assert test_context['error'] is None
        response = test_context['response']
        assert hasattr(response, 'content')
        assert hasattr(response, 'token_usage')
        assert hasattr(response, 'model')
        assert hasattr(response, 'provider')
        assert response.token_usage.input_tokens > 0
        assert response.token_usage.output_tokens > 0