from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func

from app.ai.openai_service import openai_service
from app.core.repository import ItemRepository
from app.core.logging import get_logger
from app.user.user_repository import UserRepository
from .schemas import (
    WebpageSyncRequest,
    SummarizeRequest,
    WebpageSyncResponse,
    SummarizeResponse,
)

logger = get_logger("clipper_service")


class ClipperService:
    """클리퍼 비즈니스 로직 서비스"""
    
    def __init__(self):
        self.user_repository = UserRepository()
        self.item_repository = ItemRepository()
        self.openai_service = openai_service
        logger.info("Clipper service initialized")

    async def sync_webpage(
        self, 
        session: AsyncSession,
        request_data: WebpageSyncRequest
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
