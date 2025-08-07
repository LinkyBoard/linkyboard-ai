from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func

from app.core.repository import ItemRepository, UserRepository
from .schemas import (
    WebpageSyncRequest,
    SummarizeRequest,
    WebpageSyncResponse,
    SummarizeResponse,
)


class ClipperService:
    """클리퍼 비즈니스 로직 서비스"""
    
    def __init__(self):
        self.user_repository = UserRepository()
        self.item_repository = ItemRepository()
    
    async def sync_webpage(
        self, 
        session: AsyncSession,
        request_data: WebpageSyncRequest
    ) -> WebpageSyncResponse:
        """
        Spring Boot에서 생성된 Item ID를 사용하여 동기화
        """
        try:
            # 사용자 존재 확인 및 생성
            user = await self.user_repository.get_or_create(session, user_id=request_data.user_id)

            existing_item = await self.item_repository.get_by_id(session, request_data.item_id)
            if existing_item:
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

            return WebpageSyncResponse(
                success=True,
                message="콘텐츠가 성공적으로 저장되었습니다."
            )
        
        except Exception as e:
            raise Exception(f"저장 중 오류가 발생했습니다: {str(e)}")
    
    async def generate_webpage_summary(self, request_data: SummarizeRequest) -> SummarizeResponse:
        """
        요약 생성 비즈니스 로직
        """
        try:
            # TODO: AI 서비스 호출하여 요약 생성
            # ai_response = await self.ai_service.generate_summary(
            #     request_data.url,
            #     request_data.html_content
            # )
            
            return SummarizeResponse(
                summary="이것은 웹페이지의 요약 내용입니다.",
                keywords=["키워드1", "키워드2", "키워드3"],
                category="기술"
            )
        except Exception as e:
            raise Exception(f"요약 생성 중 오류가 발생했습니다: {str(e)}")
    
# 서비스 인스턴스 생성 (싱글톤 패턴)
clipper_service = ClipperService()
