"""
Clipper Service Functional Tests (BDD Style)

클리퍼 서비스의 통합 시나리오를 Given-When-Then 형식으로 테스트
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from fastapi.testclient import TestClient
from fastapi import UploadFile
import io

from app.main import app


class TestClipperServiceFunctional:
    """Clipper Service 기능 테스트 (Given-When-Then)"""

    @pytest.fixture
    def client(self):
        """Given: 클리퍼 서비스 API가 초기화되어 있음"""
        return TestClient(app)

    @pytest.fixture
    def test_context(self):
        """Given: 테스트 컨텍스트가 준비되어 있음"""
        return {
            'user_id': 999,
            'response': None,
            'status_code': None,
            'html_file': None
        }

    @pytest.fixture
    def test_html_file(self):
        """Given: HTML 파일이 준비되어 있음"""
        html_content = """
        <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Python Programming</h1>
            <p>This is a test article about Python programming.</p>
        </body>
        </html>
        """
        return ("test.html", io.StringIO(html_content), "text/html")

    @pytest.fixture
    def large_html_file(self):
        """Given: 대용량 HTML 파일이 준비되어 있음"""
        html_content = """
        <html>
        <head><title>Large Test Page</title></head>
        <body>
            <h1>Large Content</h1>
            """ + "<p>Large content section.</p>" * 1000 + """
        </body>
        </html>
        """
        return ("large.html", io.StringIO(html_content), "text/html")

    @patch('app.board_ai.service.BoardAIService')
    def test_given_ai_service_working_when_webpage_summary_requested_then_success(
        self, mock_ai_service, client, test_context, test_html_file
    ):
        """
        Given: AI 서비스가 정상 작동함
        When: 사용자가 웹페이지 요약을 요청함
        Then: 성공적인 응답을 받아야 함
        """
        # Given
        mock_ai_service.return_value.summarize_webpage = AsyncMock(return_value={
            'summary': 'Python programming article summary',
            'tags': ['python', 'programming', 'tutorial'],
            'category': 'Technology'
        })
        
        # When
        files = {'html_file': test_html_file}
        data = {
            'user_id': test_context['user_id'],
            'url': 'http://example.com'
        }
        test_context['response'] = client.post('/v1/clipper/summarize', files=files, data=data)
        test_context['status_code'] = test_context['response'].status_code
        
        # Then
        assert test_context['status_code'] == 200
        response_json = test_context['response'].json()
        assert 'summary' in response_json
        assert 'tags' in response_json
        assert 'category' in response_json
        assert len(response_json['summary']) > 0
        assert len(response_json['tags']) > 0
        assert len(response_json['category']) > 0

    def test_given_html_file_ready_when_summary_requested_without_user_id_then_validation_error(
        self, client, test_context, test_html_file
    ):
        """
        Given: HTML 파일이 준비되어 있음
        When: 사용자 ID 없이 요약을 요청함
        Then: 검증 오류를 받아야 함
        """
        # Given & When
        files = {'html_file': test_html_file}
        data = {'url': 'http://example.com'}  # user_id missing
        test_context['response'] = client.post('/v1/clipper/summarize', files=files, data=data)
        test_context['status_code'] = test_context['response'].status_code
        
        # Then
        assert test_context['status_code'] == 422

    def test_given_no_html_file_when_summary_requested_then_validation_error(
        self, client, test_context
    ):
        """
        Given: HTML 파일이 없음
        When: 요약을 요청함
        Then: 검증 오류를 받아야 함
        """
        # Given & When
        data = {
            'user_id': test_context['user_id'],
            'url': 'http://example.com'
        }
        test_context['response'] = client.post('/v1/clipper/summarize', data=data)  # No file
        test_context['status_code'] = test_context['response'].status_code
        
        # Then
        assert test_context['status_code'] == 422

    @patch('app.board_ai.service.BoardAIService')
    def test_given_ai_service_error_when_summary_requested_then_server_error(
        self, mock_ai_service, client, test_context, test_html_file
    ):
        """
        Given: AI 서비스가 오류를 발생시킴
        When: 사용자가 요약을 요청함
        Then: 서버 오류를 받아야 함
        """
        # Given
        mock_ai_service.return_value.summarize_webpage = AsyncMock(
            side_effect=Exception("AI service error")
        )
        
        # When
        files = {'html_file': test_html_file}
        data = {
            'user_id': test_context['user_id'],
            'url': 'http://example.com'
        }
        test_context['response'] = client.post('/v1/clipper/summarize', files=files, data=data)
        test_context['status_code'] = test_context['response'].status_code
        
        # Then
        assert test_context['status_code'] == 500

    @patch('app.collect.v1.clipper.service.ClipperService')
    @patch('app.repositories.user_repository.UserRepository')
    def test_given_user_exists_when_new_item_sync_requested_then_success(
        self, mock_user_repo, mock_clipper_service, client, test_context, test_html_file
    ):
        """
        Given: 사용자가 데이터베이스에 존재함
        When: 새로운 아이템으로 동기화를 요청함
        Then: 성공적인 응답을 받아야 함
        """
        # Given
        item_id = 4001
        mock_user_repo.return_value.get_user_by_id = AsyncMock(return_value=Mock(id=test_context['user_id']))
        mock_clipper_service.return_value.sync_item = AsyncMock(return_value={
            'message': 'Item synchronized successfully',
            'item_id': item_id,
            'created': True
        })
        
        # When
        files = {'html_file': test_html_file}
        data = {
            'user_id': test_context['user_id'],
            'item_id': item_id,
            'title': 'Test Article',
            'url': 'http://example.com'
        }
        test_context['response'] = client.post('/v1/clipper/sync', files=files, data=data)
        test_context['status_code'] = test_context['response'].status_code
        
        # Then
        assert test_context['status_code'] == 200
        response_json = test_context['response'].json()
        assert 'message' in response_json
        assert 'item_id' in response_json
        assert response_json['item_id'] == item_id

    @patch('app.collect.v1.clipper.service.ClipperService')
    @patch('app.repositories.user_repository.UserRepository')
    def test_given_existing_item_when_sync_requested_then_updated(
        self, mock_user_repo, mock_clipper_service, client, test_context, test_html_file
    ):
        """
        Given: 기존 아이템이 데이터베이스에 존재함
        When: 기존 아이템 ID로 동기화를 요청함
        Then: 업데이트 성공 응답을 받아야 함
        """
        # Given
        existing_item_id = 1001
        mock_user_repo.return_value.get_user_by_id = AsyncMock(return_value=Mock(id=test_context['user_id']))
        mock_clipper_service.return_value.sync_item = AsyncMock(return_value={
            'message': 'Item updated successfully',
            'item_id': existing_item_id,
            'updated': True
        })
        
        # When
        files = {'html_file': test_html_file}
        data = {
            'user_id': test_context['user_id'],
            'item_id': existing_item_id,
            'title': 'Updated Article',
            'url': 'http://example.com'
        }
        test_context['response'] = client.post('/v1/clipper/sync', files=files, data=data)
        test_context['status_code'] = test_context['response'].status_code
        
        # Then
        assert test_context['status_code'] == 200
        response_json = test_context['response'].json()
        assert 'message' in response_json
        assert response_json['item_id'] == existing_item_id

    def test_given_no_item_id_when_sync_requested_then_validation_error(
        self, client, test_context, test_html_file
    ):
        """
        Given: 아이템 ID가 없음
        When: 동기화를 요청함
        Then: 검증 오류를 받아야 함
        """
        # Given & When
        files = {'html_file': test_html_file}
        data = {
            'user_id': test_context['user_id'],
            'title': 'Test Article',
            'url': 'http://example.com'
            # item_id missing
        }
        test_context['response'] = client.post('/v1/clipper/sync', files=files, data=data)
        test_context['status_code'] = test_context['response'].status_code
        
        # Then
        assert test_context['status_code'] == 422

    def test_given_no_html_file_when_sync_requested_then_validation_error(
        self, client, test_context
    ):
        """
        Given: HTML 파일이 없음
        When: 동기화를 요청함
        Then: 검증 오류를 받아야 함
        """
        # Given & When
        data = {
            'user_id': test_context['user_id'],
            'item_id': 4001,
            'title': 'Test Article',
            'url': 'http://example.com'
        }
        test_context['response'] = client.post('/v1/clipper/sync', data=data)  # No file
        test_context['status_code'] = test_context['response'].status_code
        
        # Then
        assert test_context['status_code'] == 422

    @patch('app.collect.v1.clipper.service.ClipperService')
    @patch('app.repositories.user_repository.UserRepository')
    def test_given_special_characters_when_sync_requested_then_properly_handled(
        self, mock_user_repo, mock_clipper_service, client, test_context, test_html_file
    ):
        """
        Given: 특수 문자가 포함된 제목이 있음
        When: 동기화를 요청함
        Then: 특수 문자가 올바르게 처리되어야 함
        """
        # Given
        special_title = "Test Article with 특수문자 & symbols!@#$%"
        item_id = 4002
        mock_user_repo.return_value.get_user_by_id = AsyncMock(return_value=Mock(id=test_context['user_id']))
        mock_clipper_service.return_value.sync_item = AsyncMock(return_value={
            'message': 'Item synchronized successfully',
            'item_id': item_id,
            'title': special_title
        })
        
        # When
        files = {'html_file': test_html_file}
        data = {
            'user_id': test_context['user_id'],
            'item_id': item_id,
            'title': special_title,
            'url': 'http://example.com'
        }
        test_context['response'] = client.post('/v1/clipper/sync', files=files, data=data)
        test_context['status_code'] = test_context['response'].status_code
        
        # Then
        assert test_context['status_code'] == 200
        response_json = test_context['response'].json()
        assert response_json['title'] == special_title

    @patch('app.collect.v1.clipper.service.ClipperService')
    @patch('app.repositories.user_repository.UserRepository')
    def test_given_large_content_when_sync_requested_then_successfully_processed(
        self, mock_user_repo, mock_clipper_service, client, test_context, large_html_file
    ):
        """
        Given: 대용량 HTML 파일이 준비되어 있음
        When: 대용량 컨텐츠로 동기화를 요청함
        Then: 성공적으로 처리되어야 함
        """
        # Given
        item_id = 4003
        mock_user_repo.return_value.get_user_by_id = AsyncMock(return_value=Mock(id=test_context['user_id']))
        mock_clipper_service.return_value.sync_item = AsyncMock(return_value={
            'message': 'Large content processed successfully',
            'item_id': item_id,
            'content_size': 'large'
        })
        
        # When
        files = {'html_file': large_html_file}
        data = {
            'user_id': test_context['user_id'],
            'item_id': item_id,
            'title': 'Large Content Article',
            'url': 'http://example.com'
        }
        test_context['response'] = client.post('/v1/clipper/sync', files=files, data=data)
        test_context['status_code'] = test_context['response'].status_code
        
        # Then
        assert test_context['status_code'] == 200
        response_json = test_context['response'].json()
        assert 'message' in response_json
        assert 'large' in response_json.get('content_size', '')

    @patch('app.board_ai.service.BoardAIService')
    def test_given_tag_count_specified_when_summary_requested_then_exact_count_returned(
        self, mock_ai_service, client, test_context, test_html_file
    ):
        """
        Given: 태그 개수가 지정됨
        When: 요약을 요청함
        Then: 정확한 개수의 태그가 반환되어야 함
        """
        # Given
        tag_count = 3
        mock_ai_service.return_value.summarize_webpage = AsyncMock(return_value={
            'summary': 'Test summary',
            'tags': ['tag1', 'tag2', 'tag3'],
            'category': 'Test'
        })
        
        # When
        files = {'html_file': test_html_file}
        data = {
            'user_id': test_context['user_id'],
            'url': 'http://example.com',
            'tag_count': tag_count
        }
        test_context['response'] = client.post('/v1/clipper/summarize', files=files, data=data)
        test_context['status_code'] = test_context['response'].status_code
        
        # Then
        assert test_context['status_code'] == 200
        response_json = test_context['response'].json()
        assert len(response_json['tags']) == tag_count

    @patch('app.board_ai.service.BoardAIService')
    def test_given_no_tag_count_when_summary_requested_then_default_count_returned(
        self, mock_ai_service, client, test_context, test_html_file
    ):
        """
        Given: 태그 개수가 지정되지 않음
        When: 요약을 요청함
        Then: 기본 개수의 태그가 반환되어야 함
        """
        # Given
        default_tags = ['tag1', 'tag2', 'tag3', 'tag4', 'tag5']  # Default 5 tags
        mock_ai_service.return_value.summarize_webpage = AsyncMock(return_value={
            'summary': 'Test summary',
            'tags': default_tags,
            'category': 'Test'
        })
        
        # When
        files = {'html_file': test_html_file}
        data = {
            'user_id': test_context['user_id'],
            'url': 'http://example.com'
            # tag_count not specified
        }
        test_context['response'] = client.post('/v1/clipper/summarize', files=files, data=data)
        test_context['status_code'] = test_context['response'].status_code
        
        # Then
        assert test_context['status_code'] == 200
        response_json = test_context['response'].json()
        assert len(response_json['tags']) == 5  # Default count