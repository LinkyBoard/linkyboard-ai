"""
Content 관리 서비스
"""

from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.logging import get_logger
from app.core.models import Item, ItemEmbeddingMetadata, ItemTags
from app.observability import trace_request, record_db_operation
from .schemas import ContentDeleteRequest

logger = get_logger(__name__)


class ContentService:
    """Content 관리 서비스"""
    
    async def delete_items(
        self, 
        session: AsyncSession, 
        request_data: ContentDeleteRequest
    ) -> Dict[str, Any]:
        """
        여러 개의 Item을 삭제합니다.
        
        Args:
            session: 데이터베이스 세션
            request_data: 삭제 요청 데이터
            
        Returns:
            삭제 결과 정보
        """
        async with trace_request(
            "content_delete_items", 
            user_id=request_data.user_id,
            item_count=len(request_data.item_ids)
        ) as span:
            
            logger.info(
                f"Starting deletion of {len(request_data.item_ids)} items for user {request_data.user_id}"
            )
            
            deleted_count = 0
            failed_items = []
            results = []
            
            try:
                # 삭제할 아이템들을 조회하여 존재 여부와 소유권 확인
                stmt = select(Item).where(
                    and_(
                        Item.id.in_(request_data.item_ids),
                        Item.user_id == request_data.user_id,
                        Item.is_active == True
                    )
                )
                result = await session.execute(stmt)
                existing_items = result.scalars().all()
                
                existing_item_ids = [item.id for item in existing_items]
                non_existing_item_ids = [
                    item_id for item_id in request_data.item_ids 
                    if item_id not in existing_item_ids
                ]
                
                logger.info(
                    f"Found {len(existing_items)} existing items, "
                    f"{len(non_existing_item_ids)} non-existing items"
                )
                
                # 존재하지 않거나 접근 권한이 없는 아이템들을 실패 목록에 추가
                for item_id in non_existing_item_ids:
                    failed_items.append(item_id)
                    results.append({
                        "item_id": item_id,
                        "status": "failed",
                        "reason": "Item not found or access denied"
                    })
                
                # 존재하는 아이템들을 하나씩 삭제
                for item in existing_items:
                    try:
                        await self._delete_single_item(session, item)
                        deleted_count += 1
                        results.append({
                            "item_id": item.id,
                            "status": "success",
                            "title": item.title
                        })
                        logger.info(f"Successfully deleted item {item.id}: {item.title}")
                        
                    except Exception as e:
                        failed_items.append(item.id)
                        results.append({
                            "item_id": item.id,
                            "status": "failed",
                            "reason": str(e)
                        })
                        logger.error(f"Failed to delete item {item.id}: {str(e)}")
                
                # 트랜잭션 커밋
                await session.commit()
                
                # 결과 요약
                success = len(failed_items) == 0
                total_requested = len(request_data.item_ids)
                
                span.set_attribute("deleted_count", deleted_count)
                span.set_attribute("failed_count", len(failed_items))
                span.set_attribute("success_rate", deleted_count / total_requested if total_requested > 0 else 0)
                
                logger.info(
                    f"Deletion completed for user {request_data.user_id}: "
                    f"{deleted_count}/{total_requested} items deleted successfully"
                )
                
                record_db_operation("delete", "items", count=deleted_count)
                
                return {
                    "success": success,
                    "deleted_count": deleted_count,
                    "failed_items": failed_items,
                    "total_requested": total_requested,
                    "results": results
                }
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to delete items for user {request_data.user_id}: {str(e)}")
                raise
    
    async def _delete_single_item(self, session: AsyncSession, item: Item) -> None:
        """
        단일 아이템과 관련된 모든 데이터를 삭제합니다.
        
        Args:
            session: 데이터베이스 세션
            item: 삭제할 아이템
        """
        # 1. 임베딩 메타데이터 삭제 (CASCADE로 자동 삭제되지만 명시적으로 처리)
        embedding_stmt = select(ItemEmbeddingMetadata).where(
            ItemEmbeddingMetadata.item_id == item.id
        )
        embedding_result = await session.execute(embedding_stmt)
        embeddings = embedding_result.scalars().all()
        
        for embedding in embeddings:
            await session.delete(embedding)
        
        # 2. 아이템 태그 연결 삭제 (CASCADE로 자동 삭제되지만 명시적으로 처리)
        item_tags_stmt = select(ItemTags).where(ItemTags.item_id == item.id)
        item_tags_result = await session.execute(item_tags_stmt)
        item_tags = item_tags_result.scalars().all()
        
        for item_tag in item_tags:
            await session.delete(item_tag)
        
        # 3. 아이템을 soft delete (is_active = False로 설정)
        # 완전 삭제 대신 비활성화로 처리하여 데이터 복구 가능성 유지
        item.is_active = False
        
        # 실제로는 물리적 삭제를 원한다면 아래 코드 사용
        # await session.delete(item)
        
        await session.flush()


# 전역 서비스 인스턴스
content_service = ContentService()


def get_content_service() -> ContentService:
    """Content 서비스 인스턴스를 반환하는 의존성 주입 함수"""
    return content_service