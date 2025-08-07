from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from app.core.models import ItemEmbeddingMetadata, Item
from app.embedding.interfaces import EmbeddingResult
from app.core.logging import get_logger

logger = get_logger("embedding_repository")


class EmbeddingRepository:
    """임베딩 데이터 관리 리포지토리"""
    
    async def save_embeddings(
        self, 
        session: AsyncSession, 
        item_id: int, 
        embedding_results: List[EmbeddingResult]
    ) -> List[ItemEmbeddingMetadata]:
        """임베딩 결과를 데이터베이스에 저장"""
        try:
            logger.info(f"Saving {len(embedding_results)} embeddings for item {item_id}")
            
            # 기존 임베딩 삭제 (재생성 시)
            await self.delete_embeddings_by_item_id(session, item_id)
            
            saved_embeddings = []
            total_chunks = len(embedding_results)
            
            for result in embedding_results:
                embedding_metadata = ItemEmbeddingMetadata(
                    item_id=item_id,
                    embedding_model=result.model_name,
                    embedding_version=result.model_version,
                    chunk_number=result.chunk_data.chunk_number,
                    chunk_content=result.chunk_data.content,
                    chunk_size=result.chunk_data.chunk_size,
                    token_count=result.chunk_data.token_count,
                    start_position=result.chunk_data.start_position,
                    end_position=result.chunk_data.end_position,
                    total_chunks=total_chunks,
                    embedding_vector=result.embedding_vector
                )
                
                session.add(embedding_metadata)
                saved_embeddings.append(embedding_metadata)
            
            await session.commit()
            logger.info(f"Successfully saved {len(saved_embeddings)} embeddings for item {item_id}")
            return saved_embeddings
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to save embeddings for item {item_id}: {str(e)}")
            raise
    
    async def get_embeddings_by_item_id(
        self, 
        session: AsyncSession, 
        item_id: int
    ) -> List[ItemEmbeddingMetadata]:
        """아이템 ID로 임베딩 조회"""
        try:
            result = await session.execute(
                select(ItemEmbeddingMetadata)
                .where(ItemEmbeddingMetadata.item_id == item_id)
                .order_by(ItemEmbeddingMetadata.chunk_number)
            )
            embeddings = result.scalars().all()
            logger.info(f"Retrieved {len(embeddings)} embeddings for item {item_id}")
            return list(embeddings)
            
        except Exception as e:
            logger.error(f"Failed to get embeddings for item {item_id}: {str(e)}")
            raise
    
    async def delete_embeddings_by_item_id(
        self, 
        session: AsyncSession, 
        item_id: int
    ) -> int:
        """아이템 ID로 임베딩 삭제"""
        try:
            result = await session.execute(
                delete(ItemEmbeddingMetadata)
                .where(ItemEmbeddingMetadata.item_id == item_id)
            )
            deleted_count = result.rowcount
            logger.info(f"Deleted {deleted_count} embeddings for item {item_id}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete embeddings for item {item_id}: {str(e)}")
            raise
    
    async def check_embedding_exists(
        self, 
        session: AsyncSession, 
        item_id: int
    ) -> bool:
        """아이템의 임베딩 존재 여부 확인"""
        try:
            result = await session.execute(
                select(ItemEmbeddingMetadata.id)
                .where(ItemEmbeddingMetadata.item_id == item_id)
                .limit(1)
            )
            exists = result.scalar() is not None
            logger.debug(f"Embedding exists for item {item_id}: {exists}")
            return exists
            
        except Exception as e:
            logger.error(f"Failed to check embedding existence for item {item_id}: {str(e)}")
            return False
    
    async def get_embedding_stats(
        self, 
        session: AsyncSession, 
        item_id: int
    ) -> Optional[dict]:
        """아이템의 임베딩 통계 정보"""
        try:
            result = await session.execute(
                select(ItemEmbeddingMetadata)
                .where(ItemEmbeddingMetadata.item_id == item_id)
                .order_by(ItemEmbeddingMetadata.chunk_number)
            )
            embeddings = result.scalars().all()
            
            if not embeddings:
                return None
            
            stats = {
                "item_id": item_id,
                "total_chunks": len(embeddings),
                "embedding_model": embeddings[0].embedding_model,
                "embedding_version": embeddings[0].embedding_version,
                "total_content_size": sum(emb.chunk_size for emb in embeddings),
                "total_tokens": sum(emb.token_count or 0 for emb in embeddings),
                "created_at": embeddings[0].created_at.isoformat() if embeddings[0].created_at else None
            }
            
            logger.debug(f"Retrieved embedding stats for item {item_id}: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get embedding stats for item {item_id}: {str(e)}")
            return None
