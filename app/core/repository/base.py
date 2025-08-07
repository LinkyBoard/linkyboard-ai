from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload

# Generic 타입 정의
ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType], ABC):
    """기본 Repository 클래스 - 공통 CRUD 기능 제공"""
    
    def __init__(self, model: type[ModelType]):
        self.model = model
    
    async def create(self, session: AsyncSession, **kwargs) -> ModelType:
        """새 엔티티 생성"""
        entity = self.model(**kwargs)
        session.add(entity)
        await session.commit()
        await session.refresh(entity)
        return entity
    
    async def get_by_id(self, session: AsyncSession, entity_id: int) -> Optional[ModelType]:
        """ID로 엔티티 조회"""
        result = await session.execute(
            select(self.model).where(self.model.id == entity_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_ids(self, session: AsyncSession, entity_ids: List[int]) -> List[ModelType]:
        """여러 ID로 엔티티 조회"""
        result = await session.execute(
            select(self.model).where(self.model.id.in_(entity_ids))
        )
        return result.scalars().all()
    
    async def get_all(
        self, 
        session: AsyncSession, 
        skip: int = 0, 
        limit: int = 100,
        **filters
    ) -> List[ModelType]:
        """모든 엔티티 조회 (페이징 포함)"""
        query = select(self.model)
        
        # 필터 적용
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.where(getattr(self.model, key) == value)
        
        query = query.offset(skip).limit(limit)
        result = await session.execute(query)
        return result.scalars().all()
    
    async def update(
        self, 
        session: AsyncSession, 
        entity_id: int, 
        **kwargs
    ) -> Optional[ModelType]:
        """엔티티 업데이트"""
        # 먼저 존재하는지 확인
        entity = await self.get_by_id(session, entity_id)
        if not entity:
            return None
        
        # 업데이트할 필드만 추출 (None 제외)
        update_data = {k: v for k, v in kwargs.items() if v is not None}
        if not update_data:
            return entity
        
        await session.execute(
            update(self.model)
            .where(self.model.id == entity_id)
            .values(**update_data)
        )
        await session.commit()
        await session.refresh(entity)
        return entity
    
    async def delete(self, session: AsyncSession, entity_id: int) -> bool:
        """엔티티 삭제"""
        result = await session.execute(
            delete(self.model).where(self.model.id == entity_id)
        )
        await session.commit()
        return result.rowcount > 0
    
    async def count(self, session: AsyncSession, **filters) -> int:
        """엔티티 개수 조회"""
        query = select(func.count(self.model.id))
        
        # 필터 적용
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.where(getattr(self.model, key) == value)
        
        result = await session.execute(query)
        return result.scalar()
    
    async def exists(self, session: AsyncSession, entity_id: int) -> bool:
        """엔티티 존재 여부 확인"""
        result = await session.execute(
            select(self.model.id).where(self.model.id == entity_id)
        )
        return result.scalar_one_or_none() is not None
    
    async def bulk_create(self, session: AsyncSession, entities_data: List[Dict[str, Any]]) -> List[ModelType]:
        """여러 엔티티 일괄 생성"""
        entities = [self.model(**data) for data in entities_data]
        session.add_all(entities)
        await session.commit()
        
        # 생성된 엔티티들을 refresh
        for entity in entities:
            await session.refresh(entity)
        
        return entities
    
    async def bulk_update(
        self, 
        session: AsyncSession, 
        updates: List[Dict[str, Any]]
    ) -> int:
        """여러 엔티티 일괄 업데이트
        
        Args:
            updates: [{"id": int, "field1": value1, "field2": value2}, ...]
        
        Returns:
            업데이트된 행의 수
        """
        if not updates:
            return 0
        
        updated_count = 0
        for update_data in updates:
            entity_id = update_data.pop("id")
            if update_data:  # 업데이트할 데이터가 있는 경우만
                result = await session.execute(
                    update(self.model)
                    .where(self.model.id == entity_id)
                    .values(**update_data)
                )
                updated_count += result.rowcount
        
        await session.commit()
        return updated_count
