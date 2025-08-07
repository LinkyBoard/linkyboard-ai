from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import ItemRepository, UserRepository
from .schemas import (
    SaveOnlyRequest,
    SummarizeRequest,
    SaveWithSummaryRequest,
    SaveOnlyResponse,
    SummarizeResponse,
    SaveWithSummaryResponse,
)


class ClipperService:
    """클리퍼 비즈니스 로직 서비스"""
    
    def __init__(self):
        self.user_repository = UserRepository()
        self.item_repository = ItemRepository()
    
    async def save_only(
        self, 
        request_data: SaveOnlyRequest, 
        user_id: int,
        session: AsyncSession
    ) -> SaveOnlyResponse:
        """
        저장만 하기 비즈니스 로직
        """
        try:
            # 사용자 존재 확인 및 생성
            user = await self.user_repository.get_or_create(session, user_id)

            item = await self.item_repository.create(
                session,
                user_id=user.id,
                item_type="webpage",
                source_url=request_data.url,
                thumbnail=request_data.thumbnail,
                title=request_data.title,
                raw_content=request_data.html_content,
                processing_status="raw",
                is_active=True
            )

            return SaveOnlyResponse(
                success=True,
                message="콘텐츠가 성공적으로 저장되었습니다.",
                item_id=str(item.id)
            )
        
        except Exception as e:
            raise Exception(f"저장 중 오류가 발생했습니다: {str(e)}")
    
    async def generate_summary(self, request_data: SummarizeRequest) -> SummarizeResponse:
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
    
    async def save_with_summary(self, request_data: SaveWithSummaryRequest) -> SaveWithSummaryResponse:
        """
        요약과 함께 저장하기 비즈니스 로직
        """
        try:
            # TODO: 완전한 데이터로 저장 처리
            # save_response = await self.storage_service.save_complete_data({
            #     "thumbnail": request_data.thumbnail,
            #     "title": request_data.title,
            #     "url": request_data.url,
            #     "summary": request_data.summary,
            #     "keywords": request_data.keywords,
            #     "category": request_data.category,
            #     "memo": request_data.memo
            # })
            
            return SaveWithSummaryResponse(
                success=True,
                message="요약과 함께 콘텐츠가 성공적으로 저장되었습니다."
            )
        except Exception as e:
            raise Exception(f"저장 중 오류가 발생했습니다: {str(e)}")



# 서비스 인스턴스 생성 (싱글톤 패턴)
clipper_service = ClipperService()
