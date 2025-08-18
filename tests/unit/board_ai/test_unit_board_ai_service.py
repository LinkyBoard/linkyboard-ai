import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from app.board_ai.service import BoardAIService
from app.board_ai.schemas import SelectedItem
from app.core.models import Item


@pytest.fixture
def mock_session():
    """데이터베이스 세션을 위한 모의(Mock) 객체"""
    return AsyncMock()


@pytest.fixture
def board_ai_service(mocker):
    """BoardAIService 인스턴스와 의존성 모킹"""
    service = BoardAIService()
    
    # model_catalog_service를 모킹
    mocker.patch('app.board_ai.service.model_catalog_service', new_callable=AsyncMock)
    mocker.patch('app.board_ai.service.openai_service', new_callable=AsyncMock)
    mocker.patch('app.board_ai.service.count_tokens', return_value=100)
    
    return service


@pytest.fixture
def sample_board_id():
    """테스트용 보드 ID"""
    return uuid4()


@pytest.fixture
def sample_user_id():
    """테스트용 사용자 ID"""
    return 12345


@pytest.fixture
def mock_model():
    """모의 모델 객체"""
    model = MagicMock()
    model.model_name = "gpt-3.5-turbo"
    model.alias = "GPT-3.5"
    model.model_type = "llm"
    model.weight_input = 1.0
    model.weight_output = 4.0
    return model


@pytest.fixture
def mock_item():
    """모의 아이템 객체"""
    item = MagicMock()
    item.id = 123
    item.title = "테스트 아이템"
    item.source_url = "https://example.com"
    item.item_type = "webpage"
    item.summary = "테스트 요약"
    item.raw_content = "테스트 내용"
    item.category = "기술"
    return item


class TestBoardAIService:
    """BoardAIService 단위 테스트"""
    
    @pytest.mark.asyncio
    async def test_ask_with_model_selection_success(
        self, 
        board_ai_service,
        sample_board_id,
        sample_user_id,
        mock_model,
        mocker
    ):
        """모델 선택을 통한 AI 질의 성공 테스트"""
        # Given
        query = "테스트 질문입니다"
        
        # model_catalog_service 모킹
        catalog_service = mocker.patch('app.board_ai.service.model_catalog_service')
        catalog_service.get_model_by_alias = AsyncMock(return_value=mock_model)
        catalog_service.get_active_models = AsyncMock(return_value=[mock_model])
        
        # openai_service 모킹
        openai_service = mocker.patch('app.board_ai.service.openai_service')
        openai_service.generate_chat_completion = AsyncMock(return_value={
            "content": "테스트 답변입니다",
            "input_tokens": 50,
            "output_tokens": 100
        })
        
        # When
        result = await board_ai_service.ask_with_model_selection(
            query=query,
            board_id=sample_board_id,
            user_id=sample_user_id,
            model="GPT-3.5"
        )
        
        # Then
        assert result["answer_md"] == "테스트 답변입니다"
        assert result["usage"]["in"] == 50
        assert result["usage"]["out"] == 100
        assert result["usage"]["wtu"] == 450  # 50 * 1.0 + 100 * 4.0
        assert result["routing"]["selected_model"] == "GPT-3.5"
        
        # 서비스 호출 확인
        catalog_service.get_model_by_alias.assert_called_once_with("GPT-3.5")
        openai_service.generate_chat_completion.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ask_with_model_selection_no_model_specified(
        self,
        board_ai_service,
        sample_board_id,
        sample_user_id,
        mock_model,
        mocker
    ):
        """모델 미지정 시 기본 모델 사용 테스트"""
        # Given
        query = "기본 모델로 질문"
        
        catalog_service = mocker.patch('app.board_ai.service.model_catalog_service')
        catalog_service.get_active_models = AsyncMock(return_value=[mock_model])
        
        openai_service = mocker.patch('app.board_ai.service.openai_service')
        openai_service.generate_chat_completion = AsyncMock(return_value={
            "content": "기본 모델 답변",
            "input_tokens": 30,
            "output_tokens": 80
        })
        
        # When
        result = await board_ai_service.ask_with_model_selection(
            query=query,
            board_id=sample_board_id,
            user_id=sample_user_id
        )
        
        # Then
        assert result["answer_md"] == "기본 모델 답변"
        assert result["routing"]["selected_model"] == "GPT-3.5"
        catalog_service.get_active_models.assert_called_once_with("llm")
    
    @pytest.mark.asyncio
    async def test_ask_with_model_selection_budget_exceeded(
        self,
        board_ai_service,
        sample_board_id,
        sample_user_id,
        mock_model,
        mocker
    ):
        """예산 초과 시 예외 발생 테스트"""
        # Given
        query = "예산 초과 질문"
        budget_wtu = 100  # 예상 WTU보다 낮은 예산
        
        catalog_service = mocker.patch('app.board_ai.service.model_catalog_service')
        catalog_service.get_model_by_alias = AsyncMock(return_value=mock_model)
        
        # When & Then
        with pytest.raises(ValueError, match="Budget exceeded"):
            await board_ai_service.ask_with_model_selection(
                query=query,
                board_id=sample_board_id,
                user_id=sample_user_id,
                model="GPT-3.5",
                budget_wtu=budget_wtu
            )
    
    @pytest.mark.asyncio
    async def test_ask_with_selected_items_success(
        self,
        board_ai_service,
        sample_board_id,
        sample_user_id,
        mock_model,
        mock_item,
        mocker
    ):
        """선택된 아이템 기반 AI 질의 성공 테스트"""
        # Given
        query = "선택된 아이템에 대한 질문"
        instruction = "아이템 내용을 요약해주세요"
        selected_items = [
            SelectedItem(item_id=123, include_summary=True, include_content=True)
        ]
        
        catalog_service = mocker.patch('app.board_ai.service.model_catalog_service')
        catalog_service.get_model_by_alias = AsyncMock(return_value=mock_model)
        
        openai_service = mocker.patch('app.board_ai.service.openai_service')
        openai_service.generate_chat_completion = AsyncMock(return_value={
            "content": "선택된 아이템 기반 답변",
            "input_tokens": 200,
            "output_tokens": 150
        })
        
        # AsyncSessionLocal 패치 - 더 직접적인 방법
        mock_session_class = mocker.patch('app.board_ai.service.AsyncSessionLocal')
        mock_session_instance = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_session_instance.execute = AsyncMock(return_value=mock_result)
        
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # When
        result = await board_ai_service.ask_with_selected_items(
            query=query,
            instruction=instruction,
            selected_items=selected_items,
            board_id=sample_board_id,
            user_id=sample_user_id,
            model="GPT-3.5"
        )
        
        # Then
        assert result["answer_md"] == "선택된 아이템 기반 답변"
        assert len(result["used_items"]) == 1
        assert result["used_items"][0]["item_id"] == 123
        assert result["used_items"][0]["title"] == "테스트 아이템"
        assert result["usage"]["in"] == 200
        assert result["usage"]["out"] == 150
    
    @pytest.mark.asyncio
    async def test_ask_with_selected_items_no_valid_items(
        self,
        board_ai_service,
        sample_board_id,
        sample_user_id,
        mock_model,
        mocker
    ):
        """유효한 아이템이 없을 때 예외 발생 테스트"""
        # Given
        query = "유효하지 않은 아이템들"
        instruction = "처리할 아이템 없음"
        selected_items = [
            SelectedItem(item_id=999, include_summary=True)  # 존재하지 않는 아이템
        ]
        
        catalog_service = mocker.patch('app.board_ai.service.model_catalog_service')
        catalog_service.get_model_by_alias = AsyncMock(return_value=mock_model)
        
        # AsyncSessionLocal 패치 - 아이템 없음
        mock_session_class = mocker.patch('app.board_ai.service.AsyncSessionLocal')
        mock_session_instance = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None  # 아이템 없음
        mock_session_instance.execute = AsyncMock(return_value=mock_result)
        
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # When & Then
        with pytest.raises(ValueError, match="선택된 아이템 중 사용할 수 있는 것이 없습니다"):
            await board_ai_service.ask_with_selected_items(
                query=query,
                instruction=instruction,
                selected_items=selected_items,
                board_id=sample_board_id,
                user_id=sample_user_id,
                model="GPT-3.5"
            )
    
    @pytest.mark.asyncio
    async def test_draft_with_model_selection_success(
        self,
        board_ai_service,
        sample_board_id,
        sample_user_id,
        mock_model,
        mocker
    ):
        """초안 작성 성공 테스트"""
        # Given
        outline = ["서론", "본론", "결론"]
        
        catalog_service = mocker.patch('app.board_ai.service.model_catalog_service')
        catalog_service.get_model_by_alias = AsyncMock(return_value=mock_model)
        
        openai_service = mocker.patch('app.board_ai.service.openai_service')
        openai_service.generate_chat_completion = AsyncMock(return_value={
            "content": "# 서론\n내용...\n\n# 본론\n내용...\n\n# 결론\n내용...",
            "input_tokens": 150,
            "output_tokens": 500
        })
        
        # When
        result = await board_ai_service.draft_with_model_selection(
            outline=outline,
            board_id=sample_board_id,
            user_id=sample_user_id,
            model="GPT-3.5"
        )
        
        # Then
        assert "서론" in result["draft_md"]
        assert "본론" in result["draft_md"]
        assert "결론" in result["draft_md"]
        assert result["outline_used"] == outline
        assert result["usage"]["in"] == 150
        assert result["usage"]["out"] == 500
        assert result["usage"]["total_wtu"] == 2150  # 150 * 1.0 + 500 * 4.0