import asyncio
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from fastapi import BackgroundTasks
from datetime import datetime

from app.ai.openai_service import openai_service
from app.core.repository import ItemRepository
from app.core.logging import get_logger
from app.user.user_repository import UserRepository
from app.ai.embedding.service import embedding_service
from .schemas import (
    WebpageSyncRequest,
    SummarizeRequest,
    WebpageSyncResponse,
    SummarizeResponse,
)

logger = get_logger("clipper_service")


class ClipperService:
    """클리퍼 비즈니스 로직 서비스"""
    
    # 처리 상태 상수 (20자 제한)
    # TODO : 이 상태 상수는 데이터베이스 모델에 맞춰야 함, 전역으로 관리 필요
    STATUS_RAW = "raw"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_SAVED = "saved"
    
    def __init__(self):
        self.user_repository = UserRepository()
        self.item_repository = ItemRepository()
        self.openai_service = openai_service
        self.embedding_service = embedding_service
        logger.info("Clipper service initialized")

    async def _process_embedding_with_monitoring(self, item_id: int, html_content: str):
        """
        백그라운드 태스크로 임베딩 처리 - EmbeddingService 사용
        """
        start_time = datetime.now()
        logger.bind(
            task_type="embedding",
            item_id=item_id,
            status="started",
            timestamp=start_time.isoformat()
        ).info(f"Starting embedding process for item {item_id}")

        try:
            # DB 세션 생성
            from app.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                # EmbeddingService에 임베딩 생성 위임
                embedding_results = await self.embedding_service.create_embeddings(
                    session=session,
                    item_id=item_id,
                    content=html_content,
                    content_type="html",
                    chunking_strategy="token_based",
                    embedding_generator="openai",
                    max_chunk_size=8000
                )
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                logger.bind(
                    task_type="embedding",
                    item_id=item_id,
                    status="completed",
                    duration_seconds=duration,
                    chunks_created=len(embedding_results),
                    timestamp=end_time.isoformat()
                ).info(f"Embedding completed for item {item_id} in {duration:.2f}s")

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.bind(
                task_type="embedding",
                item_id=item_id,
                status="failed",
                error=str(e),
                duration_seconds=duration,
                timestamp=end_time.isoformat()
            ).error(f"Embedding failed for item {item_id}: {str(e)}")

    async def sync_webpage(
        self, 
        session: AsyncSession,
        background_tasks: BackgroundTasks,
        request_data: WebpageSyncRequest,
    ) -> WebpageSyncResponse:
        """
        Spring Boot에서 생성된 Item ID를 사용하여 동기화
        """
        try:
            logger.info(f"Syncing webpage for user {request_data.user_id}, item {request_data.item_id}")
            
            # 사용자 존재 확인 및 생성
            user = await self.user_repository.get_or_create(session, user_id=request_data.user_id)
            logger.bind(database=True).info(f"User {request_data.user_id} retrieved/created")

            existing_item = await self.item_repository.get_by_id(session, request_data.item_id)
            if existing_item:
                logger.info(f"Updating existing item {request_data.item_id}")
                item = await self.item_repository.update(
                    session,
                    request_data.item_id,
                    user_id=user.id,
                    item_type="webpage",
                    title=request_data.title,
                    source_url=request_data.url,
                    thumbnail=request_data.thumbnail,
                    raw_content=request_data.html_content,
                    summary=request_data.summary,
                    category=request_data.category,
                    memo=request_data.memo,
                    tags=request_data.keywords or [],
                    processing_status="raw",
                    updated_at=func.now(),
                    is_active=True
                )
            else:
                logger.info(f"Creating new item {request_data.item_id}")
                item = await self.item_repository.create(
                    session,
                    id=request_data.item_id,
                    user_id=user.id,
                    item_type="webpage",
                    title=request_data.title,
                    source_url=request_data.url,
                    thumbnail=request_data.thumbnail,
                    raw_content=request_data.html_content,
                    summary=request_data.summary,
                    category=request_data.category,
                    memo=request_data.memo,
                    tags=request_data.keywords or [],
                    processing_status="raw",
                    is_active=True
                )

            # 백그라운드 태스크로 임베딩 처리
            if background_tasks and request_data.html_content:
                background_tasks.add_task(
                    self._process_embedding_with_monitoring,
                    request_data.item_id,
                    request_data.html_content,
                )
                logger.info(f"Background task for embedding processing added for item {request_data.item_id}")

            logger.bind(database=True).info(f"Item {request_data.item_id} saved successfully")
            return WebpageSyncResponse(
                success=True,
                message="콘텐츠가 성공적으로 저장되었습니다."
            )
        
        except Exception as e:
            logger.error(f"Failed to sync webpage for item {request_data.item_id}: {str(e)}")
            raise Exception(f"저장 중 오류가 발생했습니다: {str(e)}")
    
    async def generate_webpage_summary(self, request_data: SummarizeRequest) -> SummarizeResponse:
        """
        요약 생성 비즈니스 로직
        """
        try:
            logger.info(f"Generating summary for URL: {request_data.url}")
            
            summary = await self.openai_service.generate_webpage_summary(
                url=request_data.url,
                html_content=request_data.html_content
            )

            tags = await self.openai_service.generate_webpage_tags(
                summary = summary
            )

            category = await self.openai_service.recommend_webpage_category(
                summary = summary
            )
            
            logger.info(f"Summary generation completed for URL: {request_data.url}")
            return SummarizeResponse(
                summary=summary,
                tags=tags,
                category=category
            )
        except Exception as e:
            logger.error(f"Failed to generate summary for URL {request_data.url}: {str(e)}")
            raise Exception(f"요약 생성 중 오류가 발생했습니다: {str(e)}")
    
# 서비스 인스턴스 생성 (싱글톤 패턴)
clipper_service = ClipperService()
