"""Contents 도메인 테스트 - 예외 및 스키마"""

import pytest
from pydantic import ValidationError

from app.domains.contents.exceptions import (
    CacheNotFoundException,
    ContentAlreadyDeletedException,
    ContentNotFoundException,
    FileSizeExceededException,
    InvalidContentTypeException,
)
from app.domains.contents.models import (
    ContentType,
    EmbeddingStatus,
    SummaryStatus,
)
from app.domains.contents.schemas import (
    ContentDeleteRequest,
    ContentDeleteResponse,
    ContentListRequest,
    ContentResponse,
    ContentSyncResponse,
    PDFSyncRequest,
    WebpageSyncRequest,
    YouTubeSyncRequest,
)


class TestContentExceptions:
    """콘텐츠 예외 테스트"""

    def test_content_not_found_exception(self):
        """ContentNotFoundException 테스트"""
        exc = ContentNotFoundException(content_id=1)
        assert exc.error_code == "CONTENT_NOT_FOUND"
        assert exc.status_code == 404
        assert exc.detail_info == {"content_id": 1}

    def test_content_already_deleted_exception(self):
        """ContentAlreadyDeletedException 테스트"""
        exc = ContentAlreadyDeletedException(content_id=1)
        assert exc.error_code == "CONTENT_ALREADY_DELETED"
        assert exc.status_code == 403
        assert exc.detail_info == {"content_id": 1}

    def test_invalid_content_type_exception(self):
        """InvalidContentTypeException 테스트"""
        exc = InvalidContentTypeException(content_type="invalid")
        assert exc.error_code == "INVALID_CONTENT_TYPE"
        assert exc.status_code == 400
        assert exc.detail_info == {"content_type": "invalid"}

    def test_file_size_exceeded_exception(self):
        """FileSizeExceededException 테스트"""
        exc = FileSizeExceededException(file_size=100, max_size=50)
        assert exc.error_code == "FILE_SIZE_EXCEEDED"
        assert exc.status_code == 400
        assert exc.detail_info == {"file_size": 100, "max_size": 50}

    def test_cache_not_found_exception(self):
        """CacheNotFoundException 테스트"""
        exc = CacheNotFoundException(content_hash="abc123")
        assert exc.error_code == "CACHE_NOT_FOUND"
        assert exc.status_code == 404
        assert exc.detail_info == {"content_hash": "abc123"}


class TestWebpageSyncRequestSchema:
    """웹페이지 동기화 요청 스키마 테스트"""

    def test_webpage_sync_request_valid(self):
        """유효한 웹페이지 동기화 요청"""
        data = WebpageSyncRequest(
            content_id=1,
            user_id=100,
            url="https://example.com",
            content_hash="a" * 64,
            title="Test Page",
        )
        assert data.content_id == 1
        assert data.user_id == 100
        assert str(data.url) == "https://example.com/"
        assert data.title == "Test Page"

    def test_webpage_sync_request_with_metadata(self):
        """메타데이터 포함 웹페이지 동기화 요청"""
        data = WebpageSyncRequest(
            content_id=1,
            user_id=100,
            url="https://example.com",
            content_hash="a" * 64,
            title="Test",
            summary="Summary",
            tags=["tag1", "tag2"],
            category="tech",
            memo="Memo",
        )
        assert data.summary == "Summary"
        assert data.tags == ["tag1", "tag2"]
        assert data.category == "tech"

    def test_webpage_sync_request_validation_content_id(self):
        """content_id 검증 (0 이하 불가)"""
        with pytest.raises(ValidationError):
            WebpageSyncRequest(
                content_id=0,
                user_id=100,
                url="https://example.com",
                content_hash="a" * 64,
                title="Test",
            )

    def test_webpage_sync_request_validation_hash_length(self):
        """content_hash 길이 검증 (64자)"""
        with pytest.raises(ValidationError):
            WebpageSyncRequest(
                content_id=1,
                user_id=100,
                url="https://example.com",
                content_hash="short",
                title="Test",
            )

    def test_webpage_sync_request_validation_too_many_tags(self):
        """태그 개수 제한 검증 (최대 50개)"""
        with pytest.raises(ValidationError):
            WebpageSyncRequest(
                content_id=1,
                user_id=100,
                url="https://example.com",
                content_hash="a" * 64,
                title="Test",
                tags=[f"tag{i}" for i in range(51)],
            )


class TestYouTubeSyncRequestSchema:
    """YouTube 동기화 요청 스키마 테스트"""

    def test_youtube_sync_request_valid(self):
        """유효한 YouTube 동기화 요청"""
        data = YouTubeSyncRequest(
            content_id=1,
            user_id=100,
            url="https://youtube.com/watch?v=test",
            content_hash="b" * 64,
            title="Test Video",
        )
        assert data.content_id == 1
        assert data.title == "Test Video"


class TestPDFSyncRequestSchema:
    """PDF 동기화 요청 스키마 테스트"""

    def test_pdf_sync_request_valid(self):
        """유효한 PDF 동기화 요청"""
        data = PDFSyncRequest(
            content_id=1,
            user_id=100,
            title="Test PDF",
        )
        assert data.content_id == 1
        assert data.title == "Test PDF"

    def test_pdf_sync_request_with_metadata(self):
        """메타데이터 포함 PDF 동기화 요청"""
        data = PDFSyncRequest(
            content_id=1,
            user_id=100,
            title="Test PDF",
            summary="PDF Summary",
            tags=["research", "paper"],
            category="science",
            memo="Important",
        )
        assert data.summary == "PDF Summary"
        assert len(data.tags) == 2


class TestContentDeleteRequestSchema:
    """콘텐츠 삭제 요청 스키마 테스트"""

    def test_content_delete_request_valid(self):
        """유효한 콘텐츠 삭제 요청"""
        data = ContentDeleteRequest(
            content_ids=[1, 2, 3],
            user_id=100,
        )
        assert len(data.content_ids) == 3
        assert data.user_id == 100

    def test_content_delete_request_validation_min_length(self):
        """최소 1개 이상 필요"""
        with pytest.raises(ValidationError):
            ContentDeleteRequest(content_ids=[], user_id=100)

    def test_content_delete_request_validation_max_length(self):
        """최대 100개 제한"""
        with pytest.raises(ValidationError):
            ContentDeleteRequest(
                content_ids=list(range(1, 102)),
                user_id=100,
            )


class TestContentListRequestSchema:
    """콘텐츠 목록 조회 요청 스키마 테스트"""

    def test_content_list_request_no_filters(self):
        """필터 없는 목록 조회 요청"""
        data = ContentListRequest()
        assert data.content_type is None
        assert data.category is None
        assert data.tags is None

    def test_content_list_request_with_filters(self):
        """필터 포함 목록 조회 요청"""
        data = ContentListRequest(
            content_type=ContentType.WEBPAGE,
            category="tech",
            tags=["python", "fastapi"],
        )
        assert data.content_type == ContentType.WEBPAGE
        assert data.category == "tech"
        assert len(data.tags) == 2


class TestContentResponseSchema:
    """콘텐츠 응답 스키마 테스트"""

    def test_content_response_from_model(self):
        """모델에서 응답 스키마 생성"""
        from datetime import datetime

        from app.domains.contents.models import Content

        content = Content(
            id=1,
            user_id=100,
            content_type=ContentType.WEBPAGE,
            summary_status=SummaryStatus.PENDING,
            embedding_status=EmbeddingStatus.PENDING,
            source_url="https://example.com",
            title="Test",
            created_at=datetime.now(),
        )
        response = ContentResponse.model_validate(content)
        assert response.id == 1
        assert response.content_type == ContentType.WEBPAGE
        assert response.summary_status == SummaryStatus.PENDING
        assert response.embedding_status == EmbeddingStatus.PENDING


class TestContentSyncResponseSchema:
    """콘텐츠 동기화 응답 스키마 테스트"""

    def test_content_sync_response_webpage(self):
        """웹페이지 동기화 응답 (file_hash 없음)"""
        response = ContentSyncResponse(
            content_id=1,
            file_hash=None,
        )
        assert response.content_id == 1
        assert response.file_hash is None

    def test_content_sync_response_pdf(self):
        """PDF 동기화 응답 (file_hash 포함)"""
        response = ContentSyncResponse(
            content_id=1,
            file_hash="a" * 64,
        )
        assert response.content_id == 1
        assert response.file_hash == "a" * 64


class TestContentDeleteResponseSchema:
    """콘텐츠 삭제 응답 스키마 테스트"""

    def test_content_delete_response_all_success(self):
        """모두 성공한 삭제 응답"""
        response = ContentDeleteResponse(
            deleted_count=5,
            failed_items=[],
            total_requested=5,
        )
        assert response.deleted_count == 5
        assert len(response.failed_items) == 0
        assert response.total_requested == 5

    def test_content_delete_response_partial_failure(self):
        """일부 실패한 삭제 응답"""
        response = ContentDeleteResponse(
            deleted_count=3,
            failed_items=[4, 5],
            total_requested=5,
        )
        assert response.deleted_count == 3
        assert len(response.failed_items) == 2
        assert response.total_requested == 5
