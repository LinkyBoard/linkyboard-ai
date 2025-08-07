from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, asc
from sqlalchemy.orm import selectinload

from app.core.models import Item, ItemTag, User
from .base import BaseRepository


class ItemRepository(BaseRepository[Item]):
    """Item 전용 Repository - Item 관련 특화 기능 제공"""
    
    def __init__(self):
        super().__init__(Item)
    
    async def get_by_id_with_tags(self, session: AsyncSession, item_id: int) -> Optional[Item]:
        """태그와 함께 Item 조회"""
        result = await session.execute(
            select(Item)
            .options(selectinload(Item.tags))
            .where(Item.id == item_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_user_id(
        self, 
        session: AsyncSession, 
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        item_type: Optional[str] = None,
        processing_status: Optional[str] = None
    ) -> List[Item]:
        """사용자별 Item 조회 (필터링 포함)"""
        query = select(Item).where(Item.user_id == user_id)
        
        # 필터 적용
        if item_type:
            query = query.where(Item.item_type == item_type)
        if processing_status:
            query = query.where(Item.processing_status == processing_status)
        
        # 페이징 및 정렬
        query = query.order_by(desc(Item.created_at)).offset(skip).limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    async def get_by_source_url(self, session: AsyncSession, source_url: str) -> Optional[Item]:
        """소스 URL로 Item 조회 (중복 확인용)"""
        result = await session.execute(
            select(Item).where(Item.source_url == source_url)
        )
        return result.scalar_one_or_none()
    
    async def search_by_title_or_description(
        self,
        session: AsyncSession,
        user_id: int,
        search_term: str,
        skip: int = 0,
        limit: int = 50
    ) -> List[Item]:
        """제목이나 설명에서 키워드 검색"""
        search_pattern = f"%{search_term}%"
        
        query = select(Item).where(
            and_(
                Item.user_id == user_id,
                or_(
                    Item.title.ilike(search_pattern),
                    Item.description.ilike(search_pattern),
                    Item.summary.ilike(search_pattern)
                )
            )
        ).order_by(desc(Item.created_at)).offset(skip).limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    async def get_by_category(
        self,
        session: AsyncSession,
        user_id: int,
        category: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Item]:
        """카테고리별 Item 조회"""
        query = select(Item).where(
            and_(
                Item.user_id == user_id,
                Item.category == category
            )
        ).order_by(desc(Item.created_at)).offset(skip).limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    async def get_by_processing_status(
        self,
        session: AsyncSession,
        processing_status: str,
        user_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Item]:
        """처리 상태별 Item 조회"""
        query = select(Item).where(Item.processing_status == processing_status)
        
        if user_id:
            query = query.where(Item.user_id == user_id)
        
        query = query.order_by(asc(Item.created_at)).offset(skip).limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    async def get_items_with_tags(
        self,
        session: AsyncSession,
        user_id: int,
        tag_names: List[str],
        skip: int = 0,
        limit: int = 100
    ) -> List[Item]:
        """특정 태그들을 가진 Item 조회"""
        query = select(Item).join(ItemTag).where(
            and_(
                Item.user_id == user_id,
                ItemTag.tag.in_(tag_names)
            )
        ).distinct().order_by(desc(Item.created_at)).offset(skip).limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    async def update_processing_status(
        self,
        session: AsyncSession,
        item_id: int,
        new_status: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Item]:
        """처리 상태 업데이트 (추가 데이터 포함)"""
        update_data = {"processing_status": new_status}
        
        if additional_data:
            update_data.update(additional_data)
        
        return await self.update(session, item_id, **update_data)
    
    async def get_statistics_by_user(
        self,
        session: AsyncSession,
        user_id: int
    ) -> Dict[str, Any]:
        """사용자별 Item 통계 조회"""
        from sqlalchemy import func, case
        
        result = await session.execute(
            select(
                func.count(Item.id).label('total_items'),
                func.count(case((Item.item_type == 'webpage', 1))).label('webpage_count'),
                func.count(case((Item.item_type == 'pdf', 1))).label('pdf_count'),
                func.count(case((Item.item_type == 'youtube', 1))).label('youtube_count'),
                func.count(case((Item.processing_status == 'raw', 1))).label('raw_count'),
                func.count(case((Item.processing_status == 'processed', 1))).label('processed_count'),
                func.count(case((Item.processing_status == 'summarized', 1))).label('summarized_count'),
                func.count(case((Item.processing_status == 'embedded', 1))).label('embedded_count'),
            ).where(Item.user_id == user_id)
        )
        
        stats = result.first()
        return {
            'total_items': stats.total_items,
            'by_type': {
                'webpage': stats.webpage_count,
                'pdf': stats.pdf_count,
                'youtube': stats.youtube_count,
            },
            'by_status': {
                'raw': stats.raw_count,
                'processed': stats.processed_count,
                'summarized': stats.summarized_count,
                'embedded': stats.embedded_count,
            }
        }
    
    async def get_recent_items(
        self,
        session: AsyncSession,
        user_id: int,
        days: int = 7,
        limit: int = 20
    ) -> List[Item]:
        """최근 N일간의 Item 조회"""
        from datetime import datetime, timedelta
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(Item).where(
            and_(
                Item.user_id == user_id,
                Item.created_at >= since_date
            )
        ).order_by(desc(Item.created_at)).limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    async def bulk_update_status(
        self,
        session: AsyncSession,
        item_ids: List[int],
        new_status: str
    ) -> int:
        """여러 Item의 상태 일괄 업데이트"""
        from sqlalchemy import update
        
        result = await session.execute(
            update(Item)
            .where(Item.id.in_(item_ids))
            .values(processing_status=new_status)
        )
        await session.commit()
        return result.rowcount


# Repository 인스턴스 생성 (싱글톤 패턴)
item_repository = ItemRepository()
