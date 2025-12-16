"""Content Service 단위 테스트"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import ForbiddenException
from app.domains.contents.exceptions import ContentNotFoundException
from app.domains.contents.models import (
    Content,
    ContentType,
    EmbeddingStatus,
    SummaryStatus,
)
from app.domains.contents.schemas import (
    PDFSyncRequest,
    WebpageSyncRequest,
    YouTubeSyncRequest,
)
from app.domains.contents.service import ContentService


@pytest.fixture
def mock_session():
    """Mock AsyncSession"""
    return MagicMock()


@pytest.fixture
def mock_s3_client():
    """Mock S3Client"""
    mock_client = MagicMock()
    mock_client.calculate_file_hash.return_value = "a" * 64
    mock_client.upload_pdf.return_value = "pdfs/" + ("a" * 64) + ".pdf"
    return mock_client


@pytest.fixture
def content_service(mock_session, mock_s3_client):
    """ContentService 인스턴스"""
    service = ContentService(mock_session)
    service.s3_client = mock_s3_client
    return service


class TestContentServiceWebpage:
    """웹페이지 동기화 테스트"""

    @pytest.mark.asyncio
    async def test_sync_webpage_create_new(self, content_service):
        """새 웹페이지 생성 테스트"""
        # Given
        data = WebpageSyncRequest(
            content_id=1,
            user_id=100,
            url="https://example.com",
            content_hash="a" * 64,
            title="Test Page",
        )
        content_service.repository.get_by_url = AsyncMock(return_value=None)
        created_content = Content(
            id=1,
            user_id=100,
            content_type=ContentType.WEBPAGE,
            summary_status=SummaryStatus.PENDING,
            embedding_status=EmbeddingStatus.PENDING,
            source_url="https://example.com",
            title="Test Page",
        )
        content_service.repository.create = AsyncMock(
            return_value=created_content
        )

        # When
        with patch("app.domains.contents.service.logger"):
            result = await content_service.sync_webpage(data)

        # Then
        assert result.id == 1
        assert result.content_type == ContentType.WEBPAGE
        assert result.summary_status == SummaryStatus.PENDING
        assert result.embedding_status == EmbeddingStatus.PENDING
        content_service.repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_webpage_update_existing(self, content_service):
        """기존 웹페이지 업데이트 테스트"""
        # Given
        data = WebpageSyncRequest(
            content_id=1,
            user_id=100,
            url="https://example.com",
            content_hash="a" * 64,
            title="Updated Title",
        )
        existing_content = Content(
            id=1,
            user_id=100,
            content_type=ContentType.WEBPAGE,
            summary_status=SummaryStatus.COMPLETED,
            embedding_status=EmbeddingStatus.COMPLETED,
            source_url="https://example.com",
            title="Old Title",
        )
        content_service.repository.get_by_url = AsyncMock(
            return_value=existing_content
        )
        content_service.repository.update = AsyncMock(
            return_value=existing_content
        )

        # When
        with patch("app.domains.contents.service.logger"):
            result = await content_service.sync_webpage(data)

        # Then
        assert result.title == "Updated Title"
        assert result.summary_status == SummaryStatus.PENDING  # 상태 리셋
        assert result.embedding_status == EmbeddingStatus.PENDING  # 상태 리셋
        content_service.repository.update.assert_called_once()


class TestContentServiceYouTube:
    """YouTube 동기화 테스트"""

    @pytest.mark.asyncio
    async def test_sync_youtube_create_new(self, content_service):
        """새 YouTube 콘텐츠 생성 테스트"""
        # Given
        data = YouTubeSyncRequest(
            content_id=2,
            user_id=100,
            url="https://youtube.com/watch?v=test",
            content_hash="b" * 64,
            title="Test Video",
        )
        content_service.repository.get_by_url = AsyncMock(return_value=None)
        created_content = Content(
            id=2,
            user_id=100,
            content_type=ContentType.YOUTUBE,
            summary_status=SummaryStatus.PENDING,
            embedding_status=EmbeddingStatus.PENDING,
            source_url="https://youtube.com/watch?v=test",
            title="Test Video",
        )
        content_service.repository.create = AsyncMock(
            return_value=created_content
        )

        # When
        with patch("app.domains.contents.service.logger"):
            result = await content_service.sync_youtube(data)

        # Then
        assert result.id == 2
        assert result.content_type == ContentType.YOUTUBE
        content_service.repository.create.assert_called_once()


class TestContentServicePDF:
    """PDF 동기화 테스트"""

    @pytest.mark.asyncio
    async def test_sync_pdf_create_new(self, content_service, mock_s3_client):
        """새 PDF 생성 테스트"""
        # Given
        data = PDFSyncRequest(
            content_id=3,
            user_id=100,
            title="Test PDF",
        )
        file_content = b"test pdf content"
        file_hash = "c" * 64

        mock_s3_client.calculate_file_hash.return_value = file_hash
        content_service.repository.get_by_file_hash = AsyncMock(
            return_value=None
        )
        created_content = Content(
            id=3,
            user_id=100,
            content_type=ContentType.PDF,
            summary_status=SummaryStatus.PENDING,
            embedding_status=EmbeddingStatus.PENDING,
            file_hash=file_hash,
            title="Test PDF",
        )
        content_service.repository.create = AsyncMock(
            return_value=created_content
        )

        # When
        with patch("app.domains.contents.service.logger"):
            result, returned_hash = await content_service.sync_pdf(
                data, file_content
            )

        # Then
        assert result.id == 3
        assert result.content_type == ContentType.PDF
        assert returned_hash == file_hash
        mock_s3_client.ensure_valid_file_size.assert_called_once()
        mock_s3_client.upload_pdf.assert_called_once()
        content_service.repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_pdf_update_existing(
        self, content_service, mock_s3_client
    ):
        """기존 PDF 메타데이터 업데이트 테스트"""
        # Given
        data = PDFSyncRequest(
            content_id=3,
            user_id=100,
            title="Updated PDF Title",
        )
        file_content = b"same pdf content"
        file_hash = "d" * 64

        mock_s3_client.calculate_file_hash.return_value = file_hash
        existing_content = Content(
            id=3,
            user_id=100,
            content_type=ContentType.PDF,
            summary_status=SummaryStatus.COMPLETED,
            embedding_status=EmbeddingStatus.COMPLETED,
            file_hash=file_hash,
            title="Old PDF Title",
        )
        content_service.repository.get_by_file_hash = AsyncMock(
            return_value=existing_content
        )
        content_service.repository.update = AsyncMock(
            return_value=existing_content
        )

        # When
        with patch("app.domains.contents.service.logger"):
            result, returned_hash = await content_service.sync_pdf(
                data, file_content
            )

        # Then
        assert result.title == "Updated PDF Title"
        assert result.summary_status == SummaryStatus.PENDING  # 상태 리셋
        assert result.embedding_status == EmbeddingStatus.PENDING  # 상태 리셋
        assert returned_hash == file_hash
        # 중복 PDF이므로 S3 업로드 없이 메타데이터만 업데이트
        mock_s3_client.upload_pdf.assert_not_called()
        content_service.repository.update.assert_called_once()


class TestContentServiceGet:
    """콘텐츠 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_content_success(self, content_service):
        """콘텐츠 조회 성공 테스트"""
        # Given
        mock_content = Content(
            id=1,
            user_id=100,
            content_type=ContentType.WEBPAGE,
            summary_status=SummaryStatus.PENDING,
            embedding_status=EmbeddingStatus.PENDING,
            title="Test",
        )
        content_service.repository.get_by_id = AsyncMock(
            return_value=mock_content
        )

        # When
        result = await content_service.get_content(content_id=1, user_id=100)

        # Then
        assert result == mock_content
        content_service.repository.get_by_id.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_get_content_not_found(self, content_service):
        """콘텐츠 조회 실패 - 존재하지 않음"""
        # Given
        content_service.repository.get_by_id = AsyncMock(return_value=None)

        # When / Then
        with pytest.raises(ContentNotFoundException):
            await content_service.get_content(content_id=999, user_id=100)

    @pytest.mark.asyncio
    async def test_get_content_forbidden(self, content_service):
        """콘텐츠 조회 실패 - 다른 사용자의 콘텐츠"""
        # Given
        mock_content = Content(
            id=1,
            user_id=200,  # 다른 사용자
            content_type=ContentType.WEBPAGE,
            summary_status=SummaryStatus.PENDING,
            embedding_status=EmbeddingStatus.PENDING,
            title="Test",
        )
        content_service.repository.get_by_id = AsyncMock(
            return_value=mock_content
        )

        # When / Then
        with pytest.raises(ForbiddenException) as exc_info:
            await content_service.get_content(content_id=1, user_id=100)
        assert "다른 사용자의 콘텐츠" in exc_info.value.message


class TestContentServiceList:
    """콘텐츠 목록 조회 테스트"""

    @pytest.mark.asyncio
    async def test_list_contents(self, content_service):
        """콘텐츠 목록 조회 테스트"""
        # Given
        mock_contents = [
            Content(
                id=1,
                user_id=100,
                content_type=ContentType.WEBPAGE,
                summary_status=SummaryStatus.PENDING,
                embedding_status=EmbeddingStatus.PENDING,
                title="Content 1",
            ),
            Content(
                id=2,
                user_id=100,
                content_type=ContentType.PDF,
                summary_status=SummaryStatus.COMPLETED,
                embedding_status=EmbeddingStatus.COMPLETED,
                title="Content 2",
            ),
        ]
        content_service.repository.get_list = AsyncMock(
            return_value=mock_contents
        )
        content_service.repository.count = AsyncMock(return_value=2)

        # When
        contents, total = await content_service.list_contents(
            user_id=100, page=1, size=20
        )

        # Then
        assert len(contents) == 2
        assert total == 2
        content_service.repository.get_list.assert_called_once()
        content_service.repository.count.assert_called_once()


class TestContentServiceDelete:
    """콘텐츠 삭제 테스트"""

    @pytest.mark.asyncio
    async def test_delete_contents_success(self, content_service):
        """콘텐츠 벌크 삭제 성공 테스트"""
        # Given
        content_ids = [1, 2, 3]
        user_id = 100
        content_service.repository.soft_delete_batch = AsyncMock(
            return_value=3
        )

        # When
        with patch("app.domains.contents.service.logger"):
            result = await content_service.delete_contents(
                content_ids, user_id
            )

        # Then
        assert result.deleted_count == 3
        assert result.total_requested == 3
        assert len(result.failed_items) == 0
        content_service.repository.soft_delete_batch.assert_called_once_with(
            content_ids, user_id
        )

    @pytest.mark.asyncio
    async def test_delete_contents_partial_failure(self, content_service):
        """콘텐츠 벌크 삭제 부분 실패 테스트"""
        # Given
        content_ids = [1, 2, 3]
        user_id = 100
        # 3개 요청했지만 2개만 삭제됨
        content_service.repository.soft_delete_batch = AsyncMock(
            return_value=2
        )

        # When
        with patch("app.domains.contents.service.logger"):
            result = await content_service.delete_contents(
                content_ids, user_id
            )

        # Then
        assert result.deleted_count == 2
        assert result.total_requested == 3
        # 배치 작업에서는 어떤 항목이 실패했는지 알 수 없으므로 failed_items는 빈 리스트
        assert result.failed_items == []

    @pytest.mark.asyncio
    async def test_delete_contents_exceeds_limit(self, content_service):
        """콘텐츠 삭제 제한 초과 테스트"""
        # Given
        content_ids = list(range(1, 102))  # 101개
        user_id = 100

        # When / Then
        with pytest.raises(ValueError) as exc_info:
            await content_service.delete_contents(content_ids, user_id)
        assert "최대 100개" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_contents_db_error(self, content_service):
        """콘텐츠 삭제 DB 에러 테스트"""
        # Given
        content_ids = [1, 2]
        user_id = 100
        content_service.repository.soft_delete_batch = AsyncMock(
            side_effect=SQLAlchemyError("DB error")
        )

        # When / Then
        with patch("app.domains.contents.service.logger") as mock_logger:
            with pytest.raises(SQLAlchemyError):
                await content_service.delete_contents(content_ids, user_id)
            mock_logger.exception.assert_called_once()
