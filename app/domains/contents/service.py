"""Contents 도메인 서비스

콘텐츠 동기화 및 관리를 위한 비즈니스 로직 계층입니다.
"""

from typing import List

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException
from app.core.logging import get_logger
from app.core.middlewares.context import get_request_id
from app.core.storage import S3Client, get_s3_client
from app.domains.contents.exceptions import ContentNotFoundException
from app.domains.contents.models import (
    Content,
    ContentType,
    EmbeddingStatus,
    SummaryStatus,
)
from app.domains.contents.repository import ContentFilters, ContentRepository
from app.domains.contents.schemas import (
    ContentDeleteResponse,
    ContentListRequest,
    PDFSyncRequest,
    WebpageSyncRequest,
    YouTubeSyncRequest,
)

logger = get_logger(__name__)


class ContentService:
    """콘텐츠 서비스"""

    def __init__(
        self, session: AsyncSession, s3_client: S3Client | None = None
    ):
        self.session = session
        self.repository = ContentRepository(session)
        self.s3_client = s3_client or get_s3_client()

    async def sync_webpage(self, data: WebpageSyncRequest) -> Content:
        """웹페이지 콘텐츠 동기화

        Args:
            data: 웹페이지 동기화 데이터

        Returns:
            생성 또는 업데이트된 콘텐츠 객체

        Notes:
            - Phase 4: AI 캐시에서 content_hash 확인 필요
            - Phase 4: content_embedding_metadatas로 임베딩 복사
            - Phase 4: 태그/카테고리 사용 통계 업데이트
        """
        # content_id로 기존 레코드 확인 (Spring Boot와 ID 동기화)
        existing = await self.repository.get_by_id(
            data.content_id, include_deleted=False
        )

        if existing:
            # 업데이트
            existing.title = data.title
            existing.summary = data.summary
            existing.thumbnail = (
                str(data.thumbnail) if data.thumbnail else None
            )
            existing.memo = data.memo
            existing.tags = data.tags
            existing.category = data.category
            existing.source_url = str(data.url)
            existing.summary_status = SummaryStatus.PENDING
            existing.embedding_status = EmbeddingStatus.PENDING

            content = await self.repository.update(existing)
            action = "updated"
        else:
            # 생성
            content = Content(
                id=data.content_id,
                user_id=data.user_id,
                content_type=ContentType.WEBPAGE,
                summary_status=SummaryStatus.PENDING,
                embedding_status=EmbeddingStatus.PENDING,
                source_url=str(data.url),
                title=data.title,
                summary=data.summary,
                thumbnail=str(data.thumbnail) if data.thumbnail else None,
                memo=data.memo,
                tags=data.tags,
                category=data.category,
            )
            content = await self.repository.create(content)
            action = "created"

        logger.info(
            "Webpage synced",
            extra={
                "request_id": get_request_id(),
                "content_id": content.id,
                "user_id": data.user_id,
                "action": action,
            },
        )

        return content

    async def sync_youtube(self, data: YouTubeSyncRequest) -> Content:
        """YouTube 콘텐츠 동기화

        Args:
            data: YouTube 동기화 데이터

        Returns:
            생성 또는 업데이트된 콘텐츠 객체

        Notes:
            - Phase 4: AI 캐시에서 content_hash 확인 필요
            - Phase 4: content_embedding_metadatas로 임베딩 복사
            - Phase 4: 태그/카테고리 사용 통계 업데이트
        """
        # content_id로 기존 레코드 확인 (Spring Boot와 ID 동기화)
        existing = await self.repository.get_by_id(
            data.content_id, include_deleted=False
        )

        if existing:
            # 업데이트
            existing.title = data.title
            existing.summary = data.summary
            existing.thumbnail = (
                str(data.thumbnail) if data.thumbnail else None
            )
            existing.memo = data.memo
            existing.tags = data.tags
            existing.category = data.category
            existing.source_url = str(data.url)
            existing.summary_status = SummaryStatus.PENDING
            existing.embedding_status = EmbeddingStatus.PENDING

            content = await self.repository.update(existing)
            action = "updated"
        else:
            # 생성
            content = Content(
                id=data.content_id,
                user_id=data.user_id,
                content_type=ContentType.YOUTUBE,
                summary_status=SummaryStatus.PENDING,
                embedding_status=EmbeddingStatus.PENDING,
                source_url=str(data.url),
                title=data.title,
                summary=data.summary,
                thumbnail=str(data.thumbnail) if data.thumbnail else None,
                memo=data.memo,
                tags=data.tags,
                category=data.category,
            )
            content = await self.repository.create(content)
            action = "created"

        logger.info(
            "YouTube synced",
            extra={
                "request_id": get_request_id(),
                "content_id": content.id,
                "user_id": data.user_id,
                "action": action,
            },
        )

        return content

    async def sync_pdf(
        self, data: PDFSyncRequest, file_content: bytes
    ) -> tuple[Content, str]:
        """PDF 콘텐츠 동기화

        Args:
            data: PDF 동기화 데이터
            file_content: PDF 파일 내용 (bytes)

        Returns:
            (생성 또는 업데이트된 콘텐츠 객체, 파일 해시)

        Raises:
            StorageException: S3 업로드 실패 시

        Notes:
            - Phase 4: AI 캐시에서 content_hash 확인 필요
            - Phase 4: content_embedding_metadatas로 임베딩 복사
            - Phase 4: 태그/카테고리 사용 통계 업데이트
        """
        # 파일 해시 계산
        file_hash = self.s3_client.calculate_file_hash(file_content)

        # 파일 크기 검증
        self.s3_client.ensure_valid_file_size(len(file_content))

        # content_id로 기존 레코드 확인 (Spring Boot와 ID 동기화)
        existing = await self.repository.get_by_id(
            data.content_id, include_deleted=False
        )

        if existing:
            # 업데이트
            existing.title = data.title
            existing.summary = data.summary
            existing.memo = data.memo
            existing.tags = data.tags
            existing.category = data.category
            existing.summary_status = SummaryStatus.PENDING
            existing.embedding_status = EmbeddingStatus.PENDING

            # file_hash가 변경된 경우 S3 재업로드
            if existing.file_hash != file_hash:
                object_key = self.s3_client.upload_pdf(file_content, file_hash)
                existing.file_hash = file_hash
                logger.info(
                    "PDF re-uploaded to S3",
                    extra={
                        "request_id": get_request_id(),
                        "file_hash": file_hash,
                        "object_key": object_key,
                        "size": len(file_content),
                    },
                )

            content = await self.repository.update(existing)
            action = "updated"
        else:
            # S3 업로드 (새 파일일 때만)
            object_key = self.s3_client.upload_pdf(file_content, file_hash)

            logger.info(
                "PDF uploaded to S3",
                extra={
                    "request_id": get_request_id(),
                    "file_hash": file_hash,
                    "object_key": object_key,
                    "size": len(file_content),
                },
            )

            # 생성
            content = Content(
                id=data.content_id,
                user_id=data.user_id,
                content_type=ContentType.PDF,
                summary_status=SummaryStatus.PENDING,
                embedding_status=EmbeddingStatus.PENDING,
                file_hash=file_hash,
                title=data.title,
                summary=data.summary,
                memo=data.memo,
                tags=data.tags,
                category=data.category,
            )
            content = await self.repository.create(content)
            action = "created"

        logger.info(
            "PDF synced",
            extra={
                "request_id": get_request_id(),
                "content_id": content.id,
                "user_id": data.user_id,
                "file_hash": file_hash,
                "action": action,
            },
        )

        return content, file_hash

    async def get_content(self, content_id: int, user_id: int) -> Content:
        """콘텐츠 조회

        Args:
            content_id: 콘텐츠 ID
            user_id: 사용자 ID (소유권 확인)

        Returns:
            콘텐츠 객체

        Raises:
            ContentNotFoundException: 콘텐츠를 찾을 수 없는 경우
            ForbiddenException: 다른 사용자의 콘텐츠인 경우
        """
        content = await self.repository.get_by_id(content_id)

        if not content:
            raise ContentNotFoundException(content_id=content_id)

        # 소유권 확인
        if content.user_id != user_id:
            raise ForbiddenException(message="다른 사용자의 콘텐츠에 접근할 수 없습니다.")

        return content

    async def list_contents(
        self,
        user_id: int,
        page: int = 1,
        size: int = 20,
        filters: ContentListRequest | None = None,
    ) -> tuple[list[Content], int]:
        """콘텐츠 목록 조회

        Args:
            user_id: 사용자 ID
            page: 페이지 번호
            size: 페이지 크기
            filters: 필터 옵션

        Returns:
            (콘텐츠 목록, 전체 콘텐츠 수) 튜플
        """
        skip = (page - 1) * size

        # ContentListRequest를 ContentFilters로 변환
        content_filters = None
        if filters:
            content_filters = ContentFilters(
                content_type=filters.content_type,
                category=filters.category,
                tags=filters.tags,
                date_from=filters.date_from,
                date_to=filters.date_to,
            )

        contents = await self.repository.get_list(
            user_id=user_id,
            skip=skip,
            limit=size,
            filters=content_filters,
        )

        total = await self.repository.count(
            user_id=user_id,
            filters=content_filters,
        )

        return list(contents), total

    async def delete_contents(
        self, content_ids: list[int], user_id: int
    ) -> ContentDeleteResponse:
        """콘텐츠 벌크 삭제

        Args:
            content_ids: 삭제할 콘텐츠 ID 목록
            user_id: 사용자 ID (소유권 확인)

        Returns:
            삭제 결과

        Raises:
            SQLAlchemyError: 데이터베이스 오류 시
        """
        # 최대 100개 검증
        if len(content_ids) > 100:
            raise ValueError("한 번에 최대 100개의 콘텐츠만 삭제할 수 있습니다.")

        try:
            # 벌크 soft delete (소유권 확인 포함)
            deleted_count = await self.repository.soft_delete_batch(
                content_ids, user_id
            )

            # 실패한 항목 계산
            failed_count = len(content_ids) - deleted_count
            # 배치 작업에서는 어떤 항목이 실패했는지 알 수 없음
            failed_items: List[int] = []

            logger.info(
                "Contents deleted",
                extra={
                    "request_id": get_request_id(),
                    "user_id": user_id,
                    "deleted_count": deleted_count,
                    "failed_count": failed_count,
                    "total_requested": len(content_ids),
                },
            )

            return ContentDeleteResponse(
                deleted_count=deleted_count,
                failed_items=failed_items,
                total_requested=len(content_ids),
            )

        except SQLAlchemyError as e:
            logger.exception(
                "Failed to delete contents (DB error)",
                extra={
                    "request_id": get_request_id(),
                    "user_id": user_id,
                    "content_ids": content_ids,
                    "exception_type": type(e).__name__,
                    "exception_message": str(e),
                },
            )
            raise
