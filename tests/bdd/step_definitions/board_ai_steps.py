"""
Board AI Service BDD 스텝 정의
"""

import pytest
from pytest_bdd import given, when, then, scenarios
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.board_ai.service import BoardAIService
from app.board_ai.schemas import SelectedItem

# 시나리오 로드
scenarios('../features/board_ai_service.feature')


@pytest.fixture
def board_ai_service(mocker, bdd_mock_model_catalog_service, bdd_mock_openai_service):
    """보드 AI 서비스 인스턴스"""
    service = BoardAIService()
    return service


@pytest.fixture
def board_context():
    """보드 AI 테스트 컨텍스트"""
    return {
        'service': None,
        'user_id': None,
        'board_id': None,
        'model': None,
        'query': None,
        'instruction': None,
        'selected_items': [],
        'outline': [],
        'budget_wtu': None,
        'response': None,
        'error': None
    }


# Background steps
@given("보드 AI 서비스가 초기화되어 있음")
def board_ai_service_initialized(board_ai_service, board_context):
    """보드 AI 서비스 초기화"""
    board_context['service'] = board_ai_service


@given("사용자 ID 1001이 있음")
def user_id_1001_exists(board_context):
    """사용자 ID 설정"""
    board_context['user_id'] = 1001


@given("보드 ID가 생성되어 있음")
def board_id_generated(board_context):
    """보드 ID 생성"""
    board_context['board_id'] = uuid4()


# 모델 선택 질문 응답 시나리오
@when('사용자가 "Python의 장점은 무엇인가요?" 질문을 "gpt-3.5-turbo" 모델로 요청함')
async def ask_python_question_with_model(board_context):
    """Python 질문을 특정 모델로 요청"""
    try:
        board_context['response'] = await board_context['service'].ask_with_model_selection(
            query="Python의 장점은 무엇인가요?",
            board_id=board_context['board_id'],
            user_id=board_context['user_id'],
            model="gpt-3.5-turbo"
        )
    except Exception as e:
        board_context['error'] = e


@then("성공적인 답변을 받아야 함")
def successful_answer_received(board_context):
    """성공적인 답변 확인"""
    assert board_context['response'] is not None
    assert board_context['error'] is None


@then("답변에는 마크다운 형식의 내용이 포함되어야 함")
def answer_contains_markdown(board_context):
    """마크다운 형식 내용 확인"""
    assert 'answer_md' in board_context['response']
    assert board_context['response']['answer_md'] is not None
    assert len(board_context['response']['answer_md']) > 0


@then("사용량 정보가 포함되어야 함")
def usage_info_included(board_context):
    """사용량 정보 포함 확인"""
    assert 'usage' in board_context['response']
    usage = board_context['response']['usage']
    assert 'in' in usage
    assert 'out' in usage
    assert 'wtu' in usage


@then("라우팅 정보에 선택된 모델이 표시되어야 함")
def routing_info_shows_selected_model(board_context):
    """라우팅 정보 확인"""
    assert 'routing' in board_context['response']
    assert 'selected_model' in board_context['response']['routing']


# 예산 제한 시나리오
@given("예산 제한이 1000 WTU로 설정됨")
def budget_limit_1000_wtu(board_context):
    """예산 제한 설정"""
    board_context['budget_wtu'] = 1000


@when("사용자가 짧은 질문을 요청함")
async def ask_short_question(board_context):
    """짧은 질문 요청"""
    try:
        board_context['response'] = await board_context['service'].ask_with_model_selection(
            query="안녕?",
            board_id=board_context['board_id'],
            user_id=board_context['user_id'],
            model="gpt-3.5-turbo",
            budget_wtu=board_context['budget_wtu']
        )
    except Exception as e:
        board_context['error'] = e


@then("예산 내에서 성공적으로 처리되어야 함")
def processed_within_budget(board_context):
    """예산 내 처리 확인"""
    assert board_context['response'] is not None
    assert board_context['error'] is None


@then("사용된 WTU가 예산보다 적어야 함")
def used_wtu_less_than_budget(board_context):
    """사용된 WTU가 예산보다 적은지 확인"""
    used_wtu = board_context['response']['usage']['wtu']
    assert used_wtu < board_context['budget_wtu']


# 예산 초과 시나리오
@given("예산 제한이 10 WTU로 설정됨")
def budget_limit_10_wtu(board_context):
    """낮은 예산 제한 설정"""
    board_context['budget_wtu'] = 10


@when("사용자가 긴 질문을 요청함")
async def ask_long_question(board_context):
    """긴 질문 요청"""
    try:
        long_query = "이것은 매우 긴 질문입니다. " * 100  # 긴 질문 생성
        board_context['response'] = await board_context['service'].ask_with_model_selection(
            query=long_query,
            board_id=board_context['board_id'],
            user_id=board_context['user_id'],
            model="gpt-3.5-turbo",
            budget_wtu=board_context['budget_wtu']
        )
    except Exception as e:
        board_context['error'] = e


@then('"Budget exceeded" 오류가 발생해야 함')
def budget_exceeded_error(board_context):
    """예산 초과 오류 확인"""
    assert board_context['error'] is not None
    assert "Budget exceeded" in str(board_context['error'])


# 선택된 아이템 기반 질문 시나리오
@given("테스트 아이템이 데이터베이스에 저장되어 있음")
def test_item_in_database(board_context, bdd_test_item, mocker):
    """테스트 아이템 데이터베이스 설정"""
    # AsyncSessionLocal 모킹
    mock_session_class = mocker.patch('app.board_ai.service.AsyncSessionLocal')
    mock_session_instance = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = bdd_test_item
    mock_session_instance.execute = AsyncMock(return_value=mock_result)
    
    mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
    mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)


@given("아이템 선택 정보가 준비되어 있음")
def item_selection_ready(board_context):
    """아이템 선택 정보 준비"""
    board_context['selected_items'] = [
        SelectedItem(item_id=123, include_summary=True, include_content=True)
    ]


@when("사용자가 선택된 아이템 기반으로 질문함")
async def ask_with_selected_items(board_context):
    """선택된 아이템 기반 질문"""
    try:
        board_context['response'] = await board_context['service'].ask_with_selected_items(
            query="이 아이템에 대해 설명해주세요",
            instruction="아이템 내용을 요약해주세요",
            selected_items=board_context['selected_items'],
            board_id=board_context['board_id'],
            user_id=board_context['user_id'],
            model="gpt-3.5-turbo"
        )
    except Exception as e:
        board_context['error'] = e


@then("사용된 아이템 정보가 응답에 포함되어야 함")
def used_items_in_response(board_context):
    """사용된 아이템 정보 확인"""
    assert 'used_items' in board_context['response']
    assert len(board_context['response']['used_items']) > 0


@then("아이템의 제목과 요약이 표시되어야 함")
def item_title_and_summary_displayed(board_context):
    """아이템 제목과 요약 표시 확인"""
    used_item = board_context['response']['used_items'][0]
    assert 'title' in used_item
    assert 'item_id' in used_item


# 유효하지 않은 아이템 선택 시나리오
@given("존재하지 않는 아이템이 선택됨")
def nonexistent_item_selected(board_context, mocker):
    """존재하지 않는 아이템 선택"""
    board_context['selected_items'] = [
        SelectedItem(item_id=999, include_summary=True)
    ]
    
    # AsyncSessionLocal 모킹 - 아이템 없음
    mock_session_class = mocker.patch('app.board_ai.service.AsyncSessionLocal')
    mock_session_instance = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None  # 아이템 없음
    mock_session_instance.execute = AsyncMock(return_value=mock_result)
    
    mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
    mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)


@then('"선택된 아이템 중 사용할 수 있는 것이 없습니다" 오류가 발생해야 함')
def no_usable_items_error(board_context):
    """사용 가능한 아이템 없음 오류 확인"""
    assert board_context['error'] is not None
    assert "선택된 아이템 중 사용할 수 있는 것이 없습니다" in str(board_context['error'])


# 초안 생성 시나리오
@given('아웃라인 ["서론", "본론", "결론"]이 제공됨')
def outline_provided(board_context):
    """아웃라인 제공"""
    board_context['outline'] = ["서론", "본론", "결론"]


@when("사용자가 초안 생성을 요청함")
async def request_draft_generation(board_context):
    """초안 생성 요청"""
    try:
        board_context['response'] = await board_context['service'].draft_with_model_selection(
            outline=board_context['outline'],
            board_id=board_context['board_id'],
            user_id=board_context['user_id'],
            model="gpt-3.5-turbo"
        )
    except Exception as e:
        board_context['error'] = e


@then("성공적인 초안을 받아야 함")
def successful_draft_received(board_context):
    """성공적인 초안 확인"""
    assert board_context['response'] is not None
    assert board_context['error'] is None
    assert 'draft_md' in board_context['response']


@then("초안에는 제공된 아웃라인이 반영되어야 함")
def draft_reflects_outline(board_context):
    """초안에 아웃라인 반영 확인"""
    draft = board_context['response']['draft_md']
    assert "서론" in draft
    assert "본론" in draft
    assert "결론" in draft


@then("마크다운 형식으로 작성되어야 함")
def draft_in_markdown_format(board_context):
    """마크다운 형식 확인"""
    draft = board_context['response']['draft_md']
    assert isinstance(draft, str)
    assert len(draft) > 0


# 기본 모델 사용 시나리오
@given("활성화된 모델들이 있음")
def active_models_available(board_context):
    """활성화된 모델 사용 가능 설정"""
    pass  # 이미 fixture에서 설정됨


@when("사용자가 모델을 지정하지 않고 질문함")
async def ask_without_specifying_model(board_context):
    """모델 미지정 질문"""
    try:
        board_context['response'] = await board_context['service'].ask_with_model_selection(
            query="기본 모델로 질문합니다",
            board_id=board_context['board_id'],
            user_id=board_context['user_id']
        )
    except Exception as e:
        board_context['error'] = e


@then("기본 모델이 자동으로 선택되어야 함")
def default_model_auto_selected(board_context):
    """기본 모델 자동 선택 확인"""
    assert board_context['response'] is not None
    assert 'routing' in board_context['response']
    assert 'selected_model' in board_context['response']['routing']