"""
Board AI 서비스 테스트
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.board_ai.service import BoardAIService
from app.core.models import Item, ModelCatalog


@pytest.fixture
def board_ai_service():
    """BoardAIService 인스턴스"""
    return BoardAIService()


@pytest.fixture
def sample_items():
    """테스트용 샘플 아이템"""
    return [
        Item(
            id=1,
            title="Python 프로그래밍 가이드",
            summary="Python 기초부터 고급 활용까지 다루는 종합 가이드",
            raw_content="Python은 간단하고 읽기 쉬운 프로그래밍 언어입니다. " * 100,
            source_url="https://example.com/python-guide"
        ),
        Item(
            id=2,
            title="AI 모델 최적화 기법",
            summary="딥러닝 모델의 성능을 향상시키는 다양한 최적화 기법 소개",
            raw_content="모델 최적화는 AI 성능 향상의 핵심입니다. " * 80,
            source_url="https://example.com/ai-optimization"
        )
    ]


@pytest.fixture
def sample_model():
    """테스트용 샘플 모델"""
    return ModelCatalog(
        id=1,
        alias="GPT-4o Mini",
        model_name="gpt-4o-mini",
        provider="openai",
        model_type="llm",
        weight_input=1.0,
        weight_output=4.0
    )


@pytest.mark.asyncio
class TestBoardAIService:
    """Board AI 서비스 테스트 클래스"""

    async def test_draft_with_selected_items_successful_json_parsing(
        self, board_ai_service, sample_items, sample_model
    ):
        """제목과 초안을 성공적으로 생성하는 테스트 (JSON 파싱 성공)"""
        
        # Mock 설정
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = sample_items
        mock_session.execute.return_value = mock_result
        
        # AI 응답 Mock (JSON 형태)
        ai_response = {
            "content": '''```json
{
  "title": "Python과 AI: 프로그래밍에서 머신러닝까지",
  "content": "# Python과 AI: 프로그래밍에서 머신러닝까지\\n\\n## 개요\\n\\nPython은 AI 개발의 핵심 언어입니다.\\n\\n## Python 기초\\n\\nPython은 간단하고 읽기 쉬운 프로그래밍 언어입니다.\\n\\n## AI 모델 최적화\\n\\n모델 최적화는 AI 성능 향상의 핵심입니다."
}
```''',
            "input_tokens": 150,
            "output_tokens": 200
        }
        
        with patch('app.board_ai.service.model_catalog_service') as mock_catalog, \
             patch('app.board_ai.service.openai_service') as mock_openai:
            
            mock_catalog.get_model_by_alias = AsyncMock(return_value=sample_model)
            mock_openai.generate_chat_completion = AsyncMock(return_value=ai_response)
            
            # 테스트 실행
            result = await board_ai_service.draft_with_selected_items(
                requirements="Python과 AI에 대한 종합적인 가이드를 작성해주세요",
                selected_items=[1, 2],
                board_id=12345,
                user_id=1001,
                model_alias="GPT-4o Mini",
                session=mock_session
            )
            
            # 검증
            assert "title" in result
            assert "draft_md" in result
            assert "used_items" in result
            assert "usage" in result
            assert "model_info" in result
            
            assert result["title"] == "Python과 AI: 프로그래밍에서 머신러닝까지"
            assert "Python은 AI 개발의 핵심 언어입니다" in result["draft_md"]
            assert len(result["used_items"]) == 2
            assert result["usage"]["input_tokens"] == 150
            assert result["usage"]["output_tokens"] == 200

    async def test_draft_with_selected_items_json_parsing_failure(
        self, board_ai_service, sample_items, sample_model
    ):
        """JSON 파싱 실패 시 fallback 로직 테스트"""
        
        # Mock 설정
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = sample_items
        mock_session.execute.return_value = mock_result
        
        # AI 응답 Mock (일반 텍스트 형태)
        ai_response = {
            "content": "# Python 프로그래밍과 AI 개발 가이드\n\n이 문서는 Python과 AI에 대한 종합적인 내용을 다룹니다.",
            "input_tokens": 100,
            "output_tokens": 150
        }
        
        with patch('app.board_ai.service.model_catalog_service') as mock_catalog, \
             patch('app.board_ai.service.openai_service') as mock_openai:
            
            mock_catalog.get_model_by_alias = AsyncMock(return_value=sample_model)
            mock_openai.generate_chat_completion = AsyncMock(return_value=ai_response)
            
            # 테스트 실행
            result = await board_ai_service.draft_with_selected_items(
                requirements="Python과 AI에 대한 종합적인 가이드를 작성해주세요",
                selected_items=[1, 2],
                board_id=12345,
                user_id=1001,
                model_alias="GPT-4o Mini",
                session=mock_session
            )
            
            # 검증 - fallback 제목이 요구사항에서 추출되어야 함
            assert result["title"] == "Python과 AI에 대한 종합적인 가이드를 작성해주세요"
            assert result["draft_md"] == ai_response["content"]

    async def test_draft_with_selected_items_empty_requirements_fallback(
        self, board_ai_service, sample_items, sample_model
    ):
        """요구사항이 비어있을 때 기본 제목 사용 테스트"""
        
        # Mock 설정
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = sample_items
        mock_session.execute.return_value = mock_result
        
        # AI 응답 Mock (비정상 응답)
        ai_response = {
            "content": "일반적인 초안 내용입니다.",
            "input_tokens": 50,
            "output_tokens": 100
        }
        
        with patch('app.board_ai.service.model_catalog_service') as mock_catalog, \
             patch('app.board_ai.service.openai_service') as mock_openai:
            
            mock_catalog.get_model_by_alias = AsyncMock(return_value=sample_model)
            mock_openai.generate_chat_completion = AsyncMock(return_value=ai_response)
            
            # 테스트 실행 (빈 요구사항)
            result = await board_ai_service.draft_with_selected_items(
                requirements="",
                selected_items=[1, 2],
                board_id=12345,
                user_id=1001,
                model_alias="GPT-4o Mini",
                session=mock_session
            )
            
            # 검증 - 기본 제목 사용
            assert result["title"] == "생성된 초안"
            assert result["draft_md"] == ai_response["content"]

    async def test_draft_with_selected_items_code_block_json_parsing(
        self, board_ai_service, sample_items, sample_model
    ):
        """코드 블록 내 JSON 파싱 테스트"""
        
        # Mock 설정
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = sample_items
        mock_session.execute.return_value = mock_result
        
        # AI 응답 Mock (코드 블록 없이 직접 JSON)
        ai_response = {
            "content": '''{\n  "title": "효율적인 Python AI 개발 방법론",\n  "content": "# 효율적인 Python AI 개발 방법론\\n\\n## 서론\\n\\nPython을 활용한 AI 개발의 효율적인 접근 방법을 소개합니다."\n}''',
            "input_tokens": 120,
            "output_tokens": 180
        }
        
        with patch('app.board_ai.service.model_catalog_service') as mock_catalog, \
             patch('app.board_ai.service.openai_service') as mock_openai:
            
            mock_catalog.get_model_by_alias = AsyncMock(return_value=sample_model)
            mock_openai.generate_chat_completion = AsyncMock(return_value=ai_response)
            
            # 테스트 실행
            result = await board_ai_service.draft_with_selected_items(
                requirements="Python AI 개발 방법론을 정리해주세요",
                selected_items=[1, 2],
                board_id=12345,
                user_id=1001,
                model_alias="GPT-4o Mini",
                session=mock_session
            )
            
            # 검증
            assert result["title"] == "효율적인 Python AI 개발 방법론"
            assert "Python을 활용한 AI 개발의 효율적인 접근 방법" in result["draft_md"]

    async def test_draft_with_selected_items_no_items(
        self, board_ai_service, sample_model
    ):
        """선택된 아이템이 없을 때 테스트"""
        
        # Mock 설정
        mock_session = AsyncMock()
        
        # AI 응답 Mock
        ai_response = {
            "content": '''{"title": "기본 초안", "content": "# 기본 초안\\n\\n선택된 자료가 없지만 요구사항에 따라 작성된 초안입니다."}''',
            "input_tokens": 80,
            "output_tokens": 120
        }
        
        with patch('app.board_ai.service.model_catalog_service') as mock_catalog, \
             patch('app.board_ai.service.openai_service') as mock_openai:
            
            mock_catalog.get_model_by_alias = AsyncMock(return_value=sample_model)
            mock_openai.generate_chat_completion = AsyncMock(return_value=ai_response)
            
            # 테스트 실행
            result = await board_ai_service.draft_with_selected_items(
                requirements="기본적인 내용으로 초안을 작성해주세요",
                selected_items=[],
                board_id=12345,
                user_id=1001,
                model_alias="GPT-4o Mini",
                session=mock_session
            )
            
            # 검증
            assert result["title"] == "기본 초안"
            assert len(result["used_items"]) == 0
            assert "선택된 자료가 없지만" in result["draft_md"]

    async def test_draft_with_selected_items_model_not_found(
        self, board_ai_service, sample_items
    ):
        """모델을 찾을 수 없을 때 에러 처리 테스트"""
        
        # Mock 설정
        mock_session = AsyncMock()
        
        with patch('app.board_ai.service.model_catalog_service') as mock_catalog:
            mock_catalog.get_model_by_alias = AsyncMock(return_value=None)
            
            # 테스트 실행 및 검증
            with pytest.raises(ValueError, match="Model 'NonExistentModel' not found"):
                await board_ai_service.draft_with_selected_items(
                    requirements="테스트 요구사항",
                    selected_items=[1, 2],
                    board_id=12345,
                    user_id=1001,
                    model_alias="NonExistentModel",
                    session=mock_session
                )