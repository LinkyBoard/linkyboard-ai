"""
Clipper Service BDD 스텝 정의
"""

import pytest
from pytest_bdd import given, when, then, scenarios
from unittest.mock import AsyncMock, patch
import tempfile
import os

# 시나리오 로드
scenarios('../features/clipper_service.feature')


@pytest.fixture
def clipper_context():
    """클리퍼 테스트 컨텍스트"""
    return {
        'user_id': None,
        'url': None,
        'html_content': None,
        'tag_count': None,
        'item_id': None,
        'title': None,
        'category': None,
        'memo': None,
        'response': None,
        'error': None,
        'status_code': None,
        'temp_files': []
    }


# Background steps
@given("클리퍼 서비스 API가 초기화되어 있음")
def clipper_api_initialized(clipper_context):
    """클리퍼 서비스 API 초기화"""
    pass  # FastAPI 앱이 이미 초기화됨


@given("사용자 ID 999가 있음")
def user_id_999_exists(clipper_context):
    """사용자 ID 설정"""
    clipper_context['user_id'] = 999


# 웹페이지 요약 성공 시나리오
@given("AI 서비스가 정상 작동함")
def ai_service_working(mocker):
    """AI 서비스 정상 작동 모킹"""
    mocker.patch(
        "app.collect.v1.clipper.service.ClipperService.generate_webpage_summary_with_recommendations",
        return_value={
            "summary": "테스트 요약입니다.",
            "recommended_tags": ["pytest", "fastapi", "test"],
            "recommended_category": "개발"
        }
    )


@given('HTML 파일 "test.html"이 준비되어 있음')
def html_file_ready(clipper_context, bdd_html_content):
    """HTML 파일 준비"""
    clipper_context['html_content'] = bdd_html_content


@when('사용자가 "http://example.com" URL로 요약을 요청함')
async def request_webpage_summary(clipper_context, bdd_async_client):
    """웹페이지 요약 요청"""
    response = await bdd_async_client.post(
        "/api/v1/clipper/webpage/summarize",
        data={
            "url": "http://example.com",
            "user_id": clipper_context['user_id'],
            "tag_count": 3
        },
        files={
            "html_file": ("test.html", clipper_context['html_content'], "text/html")
        }
    )
    clipper_context['response'] = response
    clipper_context['status_code'] = response.status_code


@then("HTTP 200 응답을 받아야 함")
def http_200_response(clipper_context):
    """HTTP 200 응답 확인"""
    assert clipper_context['status_code'] == 200


@then("응답에 요약 내용이 포함되어야 함")
def response_contains_summary(clipper_context):
    """응답에 요약 포함 확인"""
    data = clipper_context['response'].json()
    assert "summary" in data
    assert data["summary"] is not None


@then("응답에 추천 태그가 포함되어야 함")
def response_contains_tags(clipper_context):
    """응답에 태그 포함 확인"""
    data = clipper_context['response'].json()
    assert "tags" in data
    assert isinstance(data["tags"], list)


@then("응답에 추천 카테고리가 포함되어야 함")
def response_contains_category(clipper_context):
    """응답에 카테고리 포함 확인"""
    data = clipper_context['response'].json()
    assert "category" in data
    assert data["category"] is not None


# 검증 오류 시나리오
@given("HTML 파일이 준비되어 있음")
def html_file_prepared(clipper_context, bdd_html_content):
    """HTML 파일 준비"""
    clipper_context['html_content'] = bdd_html_content


@when("사용자 ID 없이 요약을 요청함")
async def request_summary_without_user_id(clipper_context, bdd_async_client):
    """사용자 ID 없이 요약 요청"""
    response = await bdd_async_client.post(
        "/api/v1/clipper/webpage/summarize",
        data={"url": "http://example.com"},
        files={"html_file": ("test.html", clipper_context['html_content'], "text/html")}
    )
    clipper_context['response'] = response
    clipper_context['status_code'] = response.status_code


@then("HTTP 422 검증 오류를 받아야 함")
def http_422_validation_error(clipper_context):
    """HTTP 422 검증 오류 확인"""
    assert clipper_context['status_code'] == 422


@when("HTML 파일 없이 요약을 요청함")
async def request_summary_without_html(clipper_context, bdd_async_client):
    """HTML 파일 없이 요약 요청"""
    response = await bdd_async_client.post(
        "/api/v1/clipper/webpage/summarize",
        data={
            "url": "http://example.com",
            "user_id": clipper_context['user_id']
        }
    )
    clipper_context['response'] = response
    clipper_context['status_code'] = response.status_code


# AI 서비스 오류 시나리오
@given("AI 서비스가 오류를 발생시킴")
def ai_service_error(mocker):
    """AI 서비스 오류 모킹"""
    mocker.patch(
        "app.collect.v1.clipper.service.ClipperService.generate_webpage_summary_with_recommendations",
        side_effect=Exception("AI service unavailable")
    )


@when("사용자가 요약을 요청함")
async def request_summary_generic(clipper_context, bdd_async_client):
    """일반적인 요약 요청"""
    response = await bdd_async_client.post(
        "/api/v1/clipper/webpage/summarize",
        data={
            "url": "http://example.com",
            "user_id": clipper_context['user_id']
        },
        files={"html_file": ("test.html", clipper_context['html_content'], "text/html")}
    )
    clipper_context['response'] = response
    clipper_context['status_code'] = response.status_code


@then("HTTP 500 서버 오류를 받아야 함")
def http_500_server_error(clipper_context):
    """HTTP 500 서버 오류 확인"""
    assert clipper_context['status_code'] == 500


# 새로운 아이템 동기화 시나리오
@given("사용자가 데이터베이스에 존재함")
async def user_exists_in_database(clipper_context, bdd_async_client, bdd_db_session, bdd_test_user):
    """사용자를 데이터베이스에 추가"""
    clipper_context['user_id'] = bdd_test_user.id
    bdd_db_session.add(bdd_test_user)
    await bdd_db_session.commit()


@when("사용자가 새로운 아이템 ID 4001로 동기화를 요청함")
async def request_sync_new_item(clipper_context, bdd_async_client):
    """새로운 아이템 동기화 요청"""
    response = await bdd_async_client.post(
        "/api/v1/clipper/webpage/sync",
        data={
            "item_id": 4001,
            "user_id": clipper_context['user_id'],
            "thumbnail": "http://example.com/thumb.jpg",
            "title": "새로운 아이템",
            "url": "http://example.com/new-item",
            "category": "기술"
        },
        files={"html_file": ("new.html", clipper_context['html_content'], "text/html")}
    )
    clipper_context['response'] = response
    clipper_context['status_code'] = response.status_code


@then("응답에 성공 메시지가 포함되어야 함")
def response_contains_success_message(clipper_context):
    """응답에 성공 메시지 포함 확인"""
    data = clipper_context['response'].json()
    assert data["success"] is True


@then("데이터베이스에 새로운 아이템이 생성되어야 함")
async def new_item_created_in_database(clipper_context, bdd_db_session):
    """데이터베이스에 새 아이템 생성 확인"""
    from app.core.models import Item
    await bdd_db_session.commit()
    item = await bdd_db_session.get(Item, 4001)
    assert item is not None


# 기존 아이템 업데이트 시나리오
@given("기존 아이템이 데이터베이스에 존재함")
async def existing_item_in_database(clipper_context, bdd_db_session, mocker):
    """기존 아이템 데이터베이스 설정"""
    clipper_context['item_id'] = 4002
    
    # sync_webpage 메서드 모킹
    mocker.patch(
        "app.collect.v1.clipper.service.ClipperService.sync_webpage",
        return_value=None
    )


@when("사용자가 기존 아이템 ID로 동기화를 요청함")
async def request_sync_existing_item(clipper_context, bdd_async_client):
    """기존 아이템 동기화 요청"""
    html_content = "<html><body>Updated content</body></html>"
    response = await bdd_async_client.post(
        "/api/v1/clipper/webpage/sync",
        data={
            "user_id": clipper_context['user_id'],
            "item_id": clipper_context['item_id'],
            "title": "Updated Title",
            "url": "http://updated.com",
            "thumbnail": "http://example.com/thumb.jpg",
            "category": "업데이트"
        },
        files={"html_file": ("test.html", html_content, "text/html")}
    )
    clipper_context['response'] = response
    clipper_context['status_code'] = response.status_code


# 동기화 검증 오류 시나리오
@when("아이템 ID 없이 동기화를 요청함")
async def request_sync_without_item_id(clipper_context, bdd_async_client):
    """아이템 ID 없이 동기화 요청"""
    response = await bdd_async_client.post(
        "/api/v1/clipper/webpage/sync",
        data={
            "user_id": clipper_context['user_id'],
            "title": "Invalid"
        },
        files={"html_file": ("invalid.html", clipper_context['html_content'], "text/html")}
    )
    clipper_context['response'] = response
    clipper_context['status_code'] = response.status_code


@when("HTML 파일 없이 동기화를 요청함")
async def request_sync_without_html(clipper_context, bdd_async_client):
    """HTML 파일 없이 동기화 요청"""
    response = await bdd_async_client.post(
        "/api/v1/clipper/webpage/sync",
        data={
            "item_id": 5001,
            "user_id": clipper_context['user_id'],
            "thumbnail": "http://example.com/thumb.jpg",
            "title": "Test Item",
            "url": "http://example.com",
            "category": "테스트"
        }
    )
    clipper_context['response'] = response
    clipper_context['status_code'] = response.status_code


# 특수 문자 처리 시나리오
@when("사용자가 특수 문자가 포함된 제목으로 동기화를 요청함")
async def request_sync_with_special_chars(clipper_context, bdd_async_client):
    """특수 문자 포함 제목으로 동기화 요청"""
    response = await bdd_async_client.post(
        "/api/v1/clipper/webpage/sync",
        data={
            "item_id": 4006,
            "user_id": clipper_context['user_id'],
            "thumbnail": "http://example.com/thumb.jpg",
            "title": "특수문자 테스트 & < > \" ' 😀",
            "url": "http://example.com/special-chars",
            "category": "테스트",
            "memo": "메모에도 특수문자: & < > \" ' 😀"
        },
        files={"html_file": ("special.html", "<html><body>특수문자 & < > \" ' 😀</body></html>", "text/html")}
    )
    clipper_context['response'] = response
    clipper_context['status_code'] = response.status_code


@then("특수 문자가 올바르게 처리되어야 함")
def special_chars_handled_correctly(clipper_context):
    """특수 문자 올바른 처리 확인"""
    assert clipper_context['status_code'] == 200


# 대용량 컨텐츠 처리 시나리오
@given("대용량 HTML 파일이 준비되어 있음")
def large_html_file_prepared(clipper_context, bdd_large_html_content, mocker):
    """대용량 HTML 파일 준비"""
    clipper_context['html_content'] = bdd_large_html_content
    
    # 서비스 모킹
    mocker.patch(
        "app.collect.v1.clipper.service.ClipperService.sync_webpage",
        return_value=None
    )


@when("사용자가 대용량 컨텐츠로 동기화를 요청함")
async def request_sync_with_large_content(clipper_context, bdd_async_client):
    """대용량 컨텐츠 동기화 요청"""
    response = await bdd_async_client.post(
        "/api/v1/clipper/webpage/sync",
        data={
            "item_id": 4005,
            "user_id": clipper_context['user_id'],
            "thumbnail": "http://example.com/thumb.jpg",
            "title": "Large Content",
            "url": "http://large.com",
            "category": "테스트"
        },
        files={"html_file": ("large.html", clipper_context['html_content'], "text/html")}
    )
    clipper_context['response'] = response
    clipper_context['status_code'] = response.status_code


@then("대용량 컨텐츠가 성공적으로 처리되어야 함")
def large_content_processed_successfully(clipper_context):
    """대용량 컨텐츠 성공 처리 확인"""
    assert clipper_context['status_code'] == 200
    data = clipper_context['response'].json()
    assert data["success"] is True


# 태그 개수 지정 시나리오
@when("사용자가 3개의 태그를 요청함")
async def request_three_tags(clipper_context, bdd_async_client):
    """3개 태그 요청"""
    response = await bdd_async_client.post(
        "/api/v1/clipper/webpage/summarize",
        data={
            "url": "http://example.com",
            "user_id": clipper_context['user_id'],
            "tag_count": 3
        },
        files={"html_file": ("test.html", clipper_context['html_content'], "text/html")}
    )
    clipper_context['response'] = response
    clipper_context['status_code'] = response.status_code


@then("정확히 3개의 태그가 반환되어야 함")
def exactly_three_tags_returned(clipper_context):
    """정확히 3개 태그 반환 확인"""
    data = clipper_context['response'].json()
    assert len(data["tags"]) == 3


# 기본 태그 개수 시나리오
@when("사용자가 태그 개수를 지정하지 않고 요약을 요청함")
async def request_summary_without_tag_count(clipper_context, bdd_async_client):
    """태그 개수 미지정 요약 요청"""
    response = await bdd_async_client.post(
        "/api/v1/clipper/webpage/summarize",
        data={
            "url": "http://example.com",
            "user_id": clipper_context['user_id']
        },
        files={"html_file": ("test.html", clipper_context['html_content'], "text/html")}
    )
    clipper_context['response'] = response
    clipper_context['status_code'] = response.status_code


@then("기본 개수의 태그가 반환되어야 함")
def default_number_of_tags_returned(clipper_context):
    """기본 개수 태그 반환 확인"""
    data = clipper_context['response'].json()
    assert "tags" in data
    assert len(data["tags"]) > 0  # 기본적으로 태그가 반환되어야 함