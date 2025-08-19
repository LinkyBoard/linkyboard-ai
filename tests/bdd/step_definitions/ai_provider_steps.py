"""
AI Provider Interface BDD 스텝 정의
"""

import pytest
from pytest_bdd import given, when, then, scenarios
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.ai.providers.router import AIModelRouter
from app.ai.providers.interface import AIResponse, TokenUsage

# 시나리오 로드
scenarios('../features/ai_provider_interface.feature')


@pytest.fixture
def ai_router():
    """AI 라우터 인스턴스"""
    return AIModelRouter()


@pytest.fixture
def context():
    """테스트 컨텍스트"""
    return {
        'user_id': None,
        'board_id': None,
        'model': None,
        'messages': [],
        'content': None,
        'tag_count': None,
        'response': None,
        'error': None
    }


# Background steps
@given("AI 라우터가 초기화되어 있음")
def ai_router_initialized(ai_router, context):
    """AI 라우터 초기화"""
    context['ai_router'] = ai_router


@given("사용자 ID 1001이 있음")
def user_id_exists(context):
    """사용자 ID 설정"""
    context['user_id'] = 1001


@given("보드 ID가 생성되어 있음")
def board_id_generated(context):
    """보드 ID 생성"""
    context['board_id'] = uuid4()


# OpenAI 채팅 완성 시나리오
@given('"gpt-3.5-turbo" 모델이 사용 가능함')
def gpt_model_available(context, bdd_mock_model_catalog_service, bdd_mock_openai_service):
    """GPT 모델 사용 가능 설정"""
    context['model'] = "gpt-3.5-turbo"


@when('사용자가 "안녕하세요, 테스트 메시지입니다" 메시지로 채팅 완성을 요청함')
async def request_chat_completion(context, bdd_mock_ai_router):
    """채팅 완성 요청"""
    try:
        context['response'] = await bdd_mock_ai_router.generate_chat_completion(
            messages=[{"role": "user", "content": "안녕하세요, 테스트 메시지입니다"}],
            model=context['model'],
            user_id=context['user_id'],
            board_id=context['board_id']
        )
    except Exception as e:
        context['error'] = e


@then("성공적인 AI 응답을 받아야 함")
def successful_ai_response(context):
    """성공적인 AI 응답 확인"""
    assert context['response'] is not None
    assert context['error'] is None
    assert isinstance(context['response'], AIResponse)


@then("응답에는 컨텐츠가 포함되어야 함")
def response_contains_content(context):
    """응답 컨텐츠 확인"""
    assert context['response'].content is not None
    assert len(context['response'].content) > 0


@then("토큰 사용량이 기록되어야 함")
def token_usage_recorded(context):
    """토큰 사용량 기록 확인"""
    assert context['response'].token_usage is not None
    assert context['response'].token_usage.input_tokens > 0
    assert context['response'].token_usage.output_tokens > 0


@then("WTU가 계산되어야 함")
def wtu_calculated(context):
    """WTU 계산 확인"""
    token_usage = context['response'].token_usage
    assert token_usage.total_tokens == token_usage.input_tokens + token_usage.output_tokens


# 웹페이지 태그 생성 시나리오
@given('웹페이지 컨텐츠 "Python 프로그래밍에 대한 기사입니다"가 있음')
def webpage_content_available(context):
    """웹페이지 컨텐츠 설정"""
    context['content'] = "Python 프로그래밍에 대한 기사입니다"


@when("사용자가 5개의 태그 생성을 요청함")
async def request_tag_generation(context, bdd_mock_ai_router):
    """태그 생성 요청"""
    try:
        context['response'] = await bdd_mock_ai_router.generate_webpage_tags(
            content=context['content'],
            tag_count=5,
            model=context['model'],
            user_id=context['user_id'],
            board_id=context['board_id']
        )
    except Exception as e:
        context['error'] = e


@then("성공적인 태그 목록을 받아야 함")
def successful_tag_list(context):
    """성공적인 태그 목록 확인"""
    assert context['response'] is not None
    assert context['error'] is None
    assert isinstance(context['response'], list)


@then("태그 개수는 5개여야 함")
def tag_count_is_five(context):
    """태그 개수 확인"""
    assert len(context['response']) == 5


@then("각 태그는 유효한 문자열이어야 함")
def each_tag_is_valid_string(context):
    """각 태그 유효성 확인"""
    for tag in context['response']:
        assert isinstance(tag, str)
        assert len(tag) > 0


# 웹페이지 카테고리 추천 시나리오
@given('웹페이지 컨텐츠 "FastAPI를 이용한 REST API 개발 가이드"가 있음')
def fastapi_content_available(context):
    """FastAPI 컨텐츠 설정"""
    context['content'] = "FastAPI를 이용한 REST API 개발 가이드"


@when("사용자가 카테고리 추천을 요청함")
async def request_category_recommendation(context, bdd_mock_ai_router):
    """카테고리 추천 요청"""
    try:
        context['response'] = await bdd_mock_ai_router.recommend_webpage_category(
            content=context['content'],
            model=context['model'],
            user_id=context['user_id'],
            board_id=context['board_id']
        )
    except Exception as e:
        context['error'] = e


@then("성공적인 카테고리 추천을 받아야 함")
def successful_category_recommendation(context):
    """성공적인 카테고리 추천 확인"""
    assert context['response'] is not None
    assert context['error'] is None


@then("카테고리는 유효한 문자열이어야 함")
def category_is_valid_string(context):
    """카테고리 유효성 확인"""
    assert isinstance(context['response'], str)
    assert len(context['response']) > 0


# 오류 처리 시나리오
@given('존재하지 않는 "invalid-model" 모델이 지정됨')
def invalid_model_specified(context):
    """잘못된 모델 지정"""
    context['model'] = "invalid-model"


@when("사용자가 채팅 완성을 요청함")
async def request_chat_completion_generic(context, bdd_mock_ai_router):
    """일반적인 채팅 완성 요청"""
    try:
        context['response'] = await bdd_mock_ai_router.generate_chat_completion(
            messages=[{"role": "user", "content": "테스트 메시지"}],
            model=context['model'],
            user_id=context['user_id'],
            board_id=context['board_id']
        )
    except Exception as e:
        context['error'] = e


@then("모델을 찾을 수 없다는 오류가 발생해야 함")
def model_not_found_error(context):
    """모델 찾을 수 없음 오류 확인"""
    assert context['error'] is not None
    assert "model" in str(context['error']).lower()


# 기본 모델 사용 시나리오
@given("모델이 지정되지 않음")
def no_model_specified(context):
    """모델 미지정 설정"""
    context['model'] = None


@then("기본 모델이 자동으로 선택되어야 함")
def default_model_selected(context):
    """기본 모델 선택 확인"""
    assert context['response'] is not None
    assert context['response'].model is not None


# 시나리오 아웃라인 스텝
@given('사용자가 "테스트 질문입니다" 메시지로 채팅 완성을 요청함')
async def request_test_chat_completion(context, bdd_mock_ai_router):
    """테스트 채팅 완성 요청"""
    try:
        context['response'] = await bdd_mock_ai_router.generate_chat_completion(
            messages=[{"role": "user", "content": "테스트 질문입니다"}],
            model=context['model'],
            user_id=context['user_id'],
            board_id=context['board_id']
        )
    except Exception as e:
        context['error'] = e


@then("응답 형식이 일관되어야 함")
def response_format_consistent(context):
    """응답 형식 일관성 확인"""
    response = context['response']
    assert hasattr(response, 'content')
    assert hasattr(response, 'token_usage')
    assert hasattr(response, 'model')
    assert hasattr(response, 'provider')