"""
Board AI Service Functional Tests (BDD Style)

보드 AI 서비스의 통합 시나리오를 Given-When-Then 형식으로 테스트
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from app.board_ai.service import BoardAIService
from app.ai.providers.interface import AIResponse, TokenUsage


class TestBoardAIServiceFunctional:
    """Board AI Service 기능 테스트 (Given-When-Then)"""

    @pytest.fixture
    def board_ai_service(self):
        """Given: 보드 AI 서비스가 초기화되어 있음"""
        with patch('app.board_ai.service.AIModelRouter') as mock_router, \
             patch('app.board_ai.service.BoardAIRepository') as mock_repo, \
             patch('app.board_ai.service.ModelCatalogService') as mock_catalog, \
             patch('app.board_ai.service.UsageMeterService') as mock_usage:
            
            service = BoardAIService()
            service.ai_router = mock_router.return_value
            service.repository = mock_repo.return_value
            service.model_catalog = mock_catalog.return_value
            service.usage_meter = mock_usage.return_value
            return service

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
    async def test_given_valid_model_when_question_asked_then_successful_answer(
        self, board_ai_service, test_context
    ):
        """
        Given: 유효한 모델이 사용 가능함
        When: 사용자가 질문을 요청함
        Then: 성공적인 답변을 받아야 함
        """
        # Given
        model = "gpt-3.5-turbo"
        question = "Python의 장점은 무엇인가요?"
        
        # Mock model catalog and AI router
        board_ai_service.model_catalog.get_model_by_name.return_value = Mock(
            name=model, provider="openai", is_active=True
        )
        mock_response = AIResponse(
            content="Python은 다음과 같은 장점이 있습니다:\n- 간단한 문법\n- 풍부한 라이브러리",
            token_usage=TokenUsage(input_tokens=15, output_tokens=25, total_tokens=40),
            model=model,
            provider="openai"
        )
        board_ai_service.ai_router.generate_chat_completion = AsyncMock(return_value=mock_response)
        board_ai_service.usage_meter.can_afford.return_value = True
        board_ai_service.usage_meter.record_usage = AsyncMock()
        
        # When
        try:
            test_context['response'] = await board_ai_service.ask_question(
                user_id=test_context['user_id'],
                board_id=test_context['board_id'],
                question=question,
                model_name=model
            )
        except Exception as e:
            test_context['error'] = e
        
        # Then
        assert test_context['response'] is not None
        assert test_context['error'] is None
        assert 'content' in test_context['response']
        assert 'usage' in test_context['response']
        assert 'routing' in test_context['response']
        assert len(test_context['response']['content']) > 0
        assert test_context['response']['routing']['model'] == model

    @pytest.mark.asyncio
    async def test_given_budget_limit_when_short_question_asked_then_processed_within_budget(
        self, board_ai_service, test_context
    ):
        """
        Given: 예산 제한이 설정됨
        When: 사용자가 짧은 질문을 요청함
        Then: 예산 내에서 성공적으로 처리되어야 함
        """
        # Given
        model = "gpt-3.5-turbo"
        question = "안녕하세요"
        budget_limit = 1000
        
        # Mock services
        board_ai_service.model_catalog.get_model_by_name.return_value = Mock(
            name=model, provider="openai", is_active=True
        )
        mock_response = AIResponse(
            content="안녕하세요! 무엇을 도와드릴까요?",
            token_usage=TokenUsage(input_tokens=5, output_tokens=10, total_tokens=15),
            model=model,
            provider="openai"
        )
        board_ai_service.ai_router.generate_chat_completion = AsyncMock(return_value=mock_response)
        board_ai_service.usage_meter.can_afford.return_value = True
        board_ai_service.usage_meter.record_usage = AsyncMock()
        
        # When
        try:
            test_context['response'] = await board_ai_service.ask_question(
                user_id=test_context['user_id'],
                board_id=test_context['board_id'],
                question=question,
                model_name=model
            )
        except Exception as e:
            test_context['error'] = e
        
        # Then
        assert test_context['response'] is not None
        assert test_context['error'] is None
        assert test_context['response']['usage']['total_tokens'] < budget_limit

    @pytest.mark.asyncio
    async def test_given_low_budget_when_long_question_asked_then_budget_exceeded_error(
        self, board_ai_service, test_context
    ):
        """
        Given: 낮은 예산 제한이 설정됨
        When: 사용자가 긴 질문을 요청함
        Then: 예산 초과 오류가 발생해야 함
        """
        # Given
        model = "gpt-3.5-turbo"
        question = "매우 긴 질문입니다. " * 100  # Very long question
        
        # Mock budget exceeded
        board_ai_service.model_catalog.get_model_by_name.return_value = Mock(
            name=model, provider="openai", is_active=True
        )
        board_ai_service.usage_meter.can_afford.return_value = False
        
        # When
        try:
            test_context['response'] = await board_ai_service.ask_question(
                user_id=test_context['user_id'],
                board_id=test_context['board_id'],
                question=question,
                model_name=model
            )
        except Exception as e:
            test_context['error'] = e
        
        # Then
        assert test_context['error'] is not None
        assert "budget" in str(test_context['error']).lower()

    @pytest.mark.asyncio
    async def test_given_selected_items_when_question_asked_then_items_included_in_context(
        self, board_ai_service, test_context
    ):
        """
        Given: 선택된 아이템이 데이터베이스에 있음
        When: 사용자가 선택된 아이템 기반으로 질문함
        Then: 아이템 정보가 응답에 포함되어야 함
        """
        # Given
        model = "gpt-3.5-turbo"
        question = "이 내용에 대해 설명해주세요"
        item_ids = [uuid4()]
        
        # Mock selected items
        mock_item = Mock(
            id=item_ids[0],
            title="Python 튜토리얼",
            summary="Python 기본 문법에 대한 설명",
            content="Python은 프로그래밍 언어입니다"
        )
        board_ai_service.repository.get_items_by_ids = AsyncMock(return_value=[mock_item])
        board_ai_service.model_catalog.get_model_by_name.return_value = Mock(
            name=model, provider="openai", is_active=True
        )
        
        mock_response = AIResponse(
            content="선택된 Python 튜토리얼에 대해 설명드리겠습니다...",
            token_usage=TokenUsage(input_tokens=20, output_tokens=30, total_tokens=50),
            model=model,
            provider="openai"
        )
        board_ai_service.ai_router.generate_chat_completion = AsyncMock(return_value=mock_response)
        board_ai_service.usage_meter.can_afford.return_value = True
        board_ai_service.usage_meter.record_usage = AsyncMock()
        
        # When
        try:
            test_context['response'] = await board_ai_service.ask_question(
                user_id=test_context['user_id'],
                board_id=test_context['board_id'],
                question=question,
                model_name=model,
                selected_item_ids=item_ids
            )
        except Exception as e:
            test_context['error'] = e
        
        # Then
        assert test_context['response'] is not None
        assert test_context['error'] is None
        assert 'selected_items' in test_context['response']
        assert len(test_context['response']['selected_items']) > 0
        assert test_context['response']['selected_items'][0]['title'] == "Python 튜토리얼"

    @pytest.mark.asyncio
    async def test_given_invalid_items_when_question_asked_then_error_occurs(
        self, board_ai_service, test_context
    ):
        """
        Given: 존재하지 않는 아이템이 선택됨
        When: 사용자가 선택된 아이템 기반으로 질문함
        Then: 아이템을 찾을 수 없다는 오류가 발생해야 함
        """
        # Given
        model = "gpt-3.5-turbo"
        question = "이 내용에 대해 설명해주세요"
        invalid_item_ids = [uuid4()]
        
        # Mock no items found
        board_ai_service.repository.get_items_by_ids = AsyncMock(return_value=[])
        board_ai_service.model_catalog.get_model_by_name.return_value = Mock(
            name=model, provider="openai", is_active=True
        )
        
        # When
        try:
            test_context['response'] = await board_ai_service.ask_question(
                user_id=test_context['user_id'],
                board_id=test_context['board_id'],
                question=question,
                model_name=model,
                selected_item_ids=invalid_item_ids
            )
        except Exception as e:
            test_context['error'] = e
        
        # Then
        assert test_context['error'] is not None
        assert "아이템" in str(test_context['error'])

    @pytest.mark.asyncio
    async def test_given_outline_when_draft_generation_requested_then_structured_draft_created(
        self, board_ai_service, test_context
    ):
        """
        Given: 아웃라인이 제공됨
        When: 사용자가 초안 생성을 요청함
        Then: 구조화된 초안을 받아야 함
        """
        # Given
        model = "gpt-3.5-turbo"
        topic = "Python 프로그래밍"
        outline = ["서론", "본론", "결론"]
        
        board_ai_service.model_catalog.get_model_by_name.return_value = Mock(
            name=model, provider="openai", is_active=True
        )
        
        mock_response = AIResponse(
            content="# Python 프로그래밍\n\n## 서론\n내용...\n\n## 본론\n내용...\n\n## 결론\n내용...",
            token_usage=TokenUsage(input_tokens=25, output_tokens=50, total_tokens=75),
            model=model,
            provider="openai"
        )
        board_ai_service.ai_router.generate_chat_completion = AsyncMock(return_value=mock_response)
        board_ai_service.usage_meter.can_afford.return_value = True
        board_ai_service.usage_meter.record_usage = AsyncMock()
        
        # When
        try:
            test_context['response'] = await board_ai_service.generate_draft(
                user_id=test_context['user_id'],
                board_id=test_context['board_id'],
                topic=topic,
                outline=outline,
                model_name=model
            )
        except Exception as e:
            test_context['error'] = e
        
        # Then
        assert test_context['response'] is not None
        assert test_context['error'] is None
        assert 'content' in test_context['response']
        draft_content = test_context['response']['content']
        for section in outline:
            assert section in draft_content
        assert draft_content.startswith("#")  # Markdown format

    @pytest.mark.asyncio
    async def test_given_no_model_specified_when_question_asked_then_default_model_used(
        self, board_ai_service, test_context
    ):
        """
        Given: 활성화된 모델들이 있음
        When: 사용자가 모델을 지정하지 않고 질문함
        Then: 기본 모델이 자동으로 선택되어야 함
        """
        # Given
        question = "테스트 질문입니다"
        default_model = "gpt-3.5-turbo"
        
        # Mock default model selection
        board_ai_service.model_catalog.get_default_model.return_value = Mock(
            name=default_model, provider="openai", is_active=True
        )
        
        mock_response = AIResponse(
            content="기본 모델로 답변드립니다",
            token_usage=TokenUsage(input_tokens=10, output_tokens=15, total_tokens=25),
            model=default_model,
            provider="openai"
        )
        board_ai_service.ai_router.generate_chat_completion = AsyncMock(return_value=mock_response)
        board_ai_service.usage_meter.can_afford.return_value = True
        board_ai_service.usage_meter.record_usage = AsyncMock()
        
        # When
        try:
            test_context['response'] = await board_ai_service.ask_question(
                user_id=test_context['user_id'],
                board_id=test_context['board_id'],
                question=question,
                model_name=None  # No model specified
            )
        except Exception as e:
            test_context['error'] = e
        
        # Then
        assert test_context['response'] is not None
        assert test_context['error'] is None
        assert test_context['response']['routing']['model'] == default_model