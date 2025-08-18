"""
Content 관리 API 라우터
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from .schemas import (
    ContentDeleteRequest, 
    ContentDeleteResponse, 
    ContentDeleteBatchResponse
)
from .service import get_content_service, ContentService

logger = get_logger(__name__)

# Router 인스턴스 생성
router = APIRouter(
    prefix="/api/v1/content",
    tags=["content"],
    responses={
        400: {"description": "Bad Request"},
        404: {"description": "Not found"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)


@router.delete("/items", response_model=ContentDeleteResponse)
async def delete_items(
    request: ContentDeleteRequest,
    session: AsyncSession = Depends(get_db),
    content_service: ContentService = Depends(get_content_service)
):
    """
    Content 항목들을 삭제합니다.
    
    단일 또는 다중 Item을 삭제할 수 있습니다.
    - 존재하지 않는 Item ID나 접근 권한이 없는 경우는 실패 목록에 포함됩니다.
    - 삭제는 soft delete로 처리되어 is_active = False로 설정됩니다.
    - 관련된 임베딩 메타데이터와 태그 연결도 함께 삭제됩니다.
    """
    try:
        logger.info(
            f"Received content delete request for user {request.user_id}, "
            f"items: {request.item_ids}"
        )
        
        # 서비스 레이어 호출
        result = await content_service.delete_items(session, request)
        
        # 응답 생성
        success = result["success"]
        deleted_count = result["deleted_count"]
        total_requested = result["total_requested"]
        failed_items = result["failed_items"]
        
        if success:
            message = f"{deleted_count}개의 콘텐츠가 성공적으로 삭제되었습니다."
        else:
            message = (
                f"{deleted_count}/{total_requested}개의 콘텐츠가 삭제되었습니다. "
                f"{len(failed_items)}개의 항목에서 오류가 발생했습니다."
            )
        
        logger.info(
            f"Content deletion completed for user {request.user_id}: "
            f"{deleted_count}/{total_requested} items deleted"
        )
        
        return ContentDeleteResponse(
            success=success,
            message=message,
            deleted_count=deleted_count,
            failed_items=failed_items,
            total_requested=total_requested
        )
        
    except Exception as e:
        logger.error(f"Failed to delete content items: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"콘텐츠 삭제 중 오류가 발생했습니다: {str(e)}"
        )


@router.delete("/items/batch", response_model=ContentDeleteBatchResponse)
async def delete_items_batch(
    request: ContentDeleteRequest,
    session: AsyncSession = Depends(get_db),
    content_service: ContentService = Depends(get_content_service)
):
    """
    Content 항목들을 배치로 삭제하고 상세한 결과를 반환합니다.
    
    각 Item별 삭제 결과와 상세한 오류 정보를 제공합니다.
    """
    try:
        logger.info(
            f"Received content batch delete request for user {request.user_id}, "
            f"items: {request.item_ids}"
        )
        
        # 서비스 레이어 호출
        result = await content_service.delete_items(session, request)
        
        # 상세 응답 생성
        success = result["success"]
        deleted_count = result["deleted_count"]
        total_requested = result["total_requested"]
        failed_items = result["failed_items"]
        results = result["results"]
        
        summary = {
            "total_requested": total_requested,
            "deleted_count": deleted_count,
            "failed_count": len(failed_items),
            "success_rate": deleted_count / total_requested if total_requested > 0 else 0
        }
        
        if success:
            message = f"모든 콘텐츠가 성공적으로 삭제되었습니다."
        else:
            message = (
                f"배치 삭제가 부분적으로 완료되었습니다. "
                f"성공: {deleted_count}개, 실패: {len(failed_items)}개"
            )
        
        logger.info(
            f"Content batch deletion completed for user {request.user_id}: "
            f"{deleted_count}/{total_requested} items deleted"
        )
        
        return ContentDeleteBatchResponse(
            success=success,
            message=message,
            results=results,
            summary=summary
        )
        
    except Exception as e:
        logger.error(f"Failed to batch delete content items: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"콘텐츠 배치 삭제 중 오류가 발생했습니다: {str(e)}"
        )