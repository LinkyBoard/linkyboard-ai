"""
Item 관리 API 라우터
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from .schemas import ItemDeleteRequest, ItemDeleteResponse
from .service import get_content_service, ContentService

logger = get_logger(__name__)

# Router 인스턴스 생성
router = APIRouter(
    prefix="/api/v1/items",
    tags=["items"],
    responses={
        400: {"description": "Bad Request"},
        404: {"description": "Not found"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)


@router.delete("", response_model=ItemDeleteResponse)
async def delete_items(
    request: ItemDeleteRequest,
    session: AsyncSession = Depends(get_db),
    content_service: ContentService = Depends(get_content_service)
):
    """
    Item들을 삭제합니다.
    
    단일 또는 다중 Item을 삭제할 수 있습니다.
    - 존재하지 않는 Item ID나 접근 권한이 없는 경우는 실패 목록에 포함됩니다.
    - 삭제는 soft delete로 처리되어 is_active = False로 설정됩니다.
    - 관련된 임베딩 메타데이터와 태그 연결도 함께 삭제됩니다.
    - 각 Item별 상세한 삭제 결과를 포함하여 반환합니다.
    """
    try:
        logger.info(
            f"Received item delete request for user {request.user_id}, "
            f"items: {request.item_ids}"
        )
        
        # 서비스 레이어 호출
        result = await content_service.delete_items(session, request)
        
        # 응답 생성
        success = result["success"]
        deleted_count = result["deleted_count"]
        total_requested = result["total_requested"]
        failed_items = result["failed_items"]
        results = result["results"]
        
        if success:
            message = f"{deleted_count}개의 아이템이 성공적으로 삭제되었습니다."
        else:
            message = (
                f"{deleted_count}/{total_requested}개의 아이템이 삭제되었습니다. "
                f"{len(failed_items)}개의 항목에서 오류가 발생했습니다."
            )
        
        logger.info(
            f"Item deletion completed for user {request.user_id}: "
            f"{deleted_count}/{total_requested} items deleted"
        )
        
        return ItemDeleteResponse(
            success=success,
            message=message,
            deleted_count=deleted_count,
            failed_items=failed_items,
            total_requested=total_requested,
            results=results
        )
        
    except Exception as e:
        logger.error(f"Failed to delete items: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"아이템 삭제 중 오류가 발생했습니다: {str(e)}"
        )