"""
Board Sync Router - 보드 동기화 API 라우터
"""

from typing import List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.core.logging import get_logger
from app.board_sync.schemas import (
    BoardSyncRequest, BoardItemSyncRequest, BoardDeleteRequest,
    BoardSyncResponse, BoardItemSyncResponse, BoardAnalyticsResponse,
    BoardListResponse, BoardAnalyticsRequest,
    MemoItemCreateRequest, MemoItemCreateResponse
)
from app.board_sync.service import board_sync_service

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/boards", tags=["Board Sync"])


@router.post("/sync", response_model=BoardSyncResponse)
async def sync_board(
    request: BoardSyncRequest,
    background_tasks: BackgroundTasks
):
    """
    보드 정보 동기화
    
    스프링 서버에서 보드 생성/수정 시 AI 서버로 동기화
    """
    try:
        logger.info(f"Syncing board {request.board_id} for user {request.user_id}")
        
        response = await board_sync_service.sync_board(request)
        
        # 분석 트리거가 필요한 경우 백그라운드 작업으로 실행
        if response.analytics_triggered:
            background_tasks.add_task(
                board_sync_service.trigger_board_analysis,
                request.board_id
            )
        
        return response
        
    except Exception as e:
        logger.error(f"Board sync failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"보드 동기화 실패: {str(e)}")


@router.post("/{board_id}/items/sync", response_model=BoardItemSyncResponse)
async def sync_board_items(
    board_id: int,
    request: BoardItemSyncRequest,
    background_tasks: BackgroundTasks
):
    """
    보드 아이템 관계 동기화
    
    스프링 서버에서 보드 아이템 추가/제거 시 AI 서버로 동기화
    """
    try:
        if request.board_id != board_id:
            raise HTTPException(status_code=400, detail="Board ID mismatch")
        
        logger.info(f"Syncing {len(request.item_ids)} items for board {board_id}")
        
        response = await board_sync_service.sync_board_items(request)
        
        # 분석 트리거가 필요한 경우 백그라운드 작업으로 실행
        if response.analytics_triggered:
            background_tasks.add_task(
                board_sync_service.trigger_board_analysis,
                board_id
            )
        
        return response
        
    except Exception as e:
        logger.error(f"Board items sync failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"보드 아이템 동기화 실패: {str(e)}")


@router.delete("/{board_id}", response_model=BoardSyncResponse)
async def delete_board(board_id: int, request: BoardDeleteRequest):
    """
    보드 삭제 (비활성화)
    
    스프링 서버에서 보드 삭제 시 AI 서버에서 비활성화
    """
    try:
        if request.board_id != board_id:
            raise HTTPException(status_code=400, detail="Board ID mismatch")
        
        logger.info(f"Deleting board {board_id} for user {request.user_id}")
        
        response = await board_sync_service.delete_board(board_id, request.user_id)
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Board delete failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"보드 삭제 실패: {str(e)}")


@router.get("/{board_id}/analytics", response_model=BoardAnalyticsResponse)
async def get_board_analytics(board_id: int):
    """
    보드 분석 정보 조회
    
    보드의 주제 분석, 카테고리 분포, 품질 지표 등을 반환
    """
    try:
        logger.info(f"Getting analytics for board {board_id}")
        
        analytics = await board_sync_service.get_board_analytics(board_id)
        
        if not analytics:
            raise HTTPException(status_code=404, detail="Board not found")
        
        return analytics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get board analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"보드 분석 정보 조회 실패: {str(e)}")


@router.post("/{board_id}/analyze")
async def trigger_board_analysis(
    board_id: int,
    request: BoardAnalyticsRequest,
    background_tasks: BackgroundTasks
):
    """
    보드 분석 트리거
    
    수동으로 보드 분석을 트리거하거나 강제 재분석 요청
    """
    try:
        if request.board_id != board_id:
            raise HTTPException(status_code=400, detail="Board ID mismatch")
        
        logger.info(f"Manually triggering analysis for board {board_id}, force_refresh={request.force_refresh}")
        
        # 백그라운드 작업으로 분석 실행
        background_tasks.add_task(
            board_sync_service.trigger_board_analysis,
            board_id,
            request.force_refresh
        )
        
        return {
            "success": True,
            "board_id": board_id,
            "message": "Board analysis triggered",
            "force_refresh": request.force_refresh
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger board analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"보드 분석 트리거 실패: {str(e)}")


@router.get("/user/{user_id}", response_model=BoardListResponse)
async def get_user_boards(user_id: int, include_inactive: bool = False):
    """
    사용자의 보드 목록 조회
    
    사용자가 소유한 모든 보드 정보와 분석 상태를 반환
    """
    try:
        logger.info(f"Getting boards for user {user_id}")
        
        boards = await board_sync_service.get_user_boards(user_id, include_inactive)
        
        analyzed_count = sum(1 for board in boards if board.get("is_analyzed", False))
        
        return BoardListResponse(
            boards=boards,
            total_count=len(boards),
            analyzed_count=analyzed_count
        )
        
    except Exception as e:
        logger.error(f"Failed to get user boards: {str(e)}")
        raise HTTPException(status_code=500, detail=f"사용자 보드 조회 실패: {str(e)}")


@router.get("/{board_id}/insights")
async def get_board_insights(board_id: int):
    """
    보드 인사이트 조회
    
    보드 분석 결과를 바탕으로 개선 제안, 콘텐츠 품질 평가 등 인사이트 제공
    """
    try:
        from app.board_analytics.service import board_analytics_service
        
        logger.info(f"Getting insights for board {board_id}")
        
        insights = await board_analytics_service.get_board_insights(board_id)
        
        if not insights:
            raise HTTPException(status_code=404, detail="Board insights not available")
        
        return insights
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get board insights: {str(e)}")
        raise HTTPException(status_code=500, detail=f"보드 인사이트 조회 실패: {str(e)}")


@router.post("/{board_id}/memo-items", response_model=MemoItemCreateResponse)
async def create_memo_item(
    board_id: int,
    request: MemoItemCreateRequest,
    background_tasks: BackgroundTasks
):
    """
    메모 아이템 생성
    
    사용자가 보드에서 직접 작성하는 메모 아이템을 생성합니다.
    clipper와 달리 제목과 내용만 포함하며, 자동으로 보드에 연결됩니다.
    """
    try:
        logger.info(f"Creating memo item for board {board_id}: {request.title[:50]}...")
        
        response = await board_sync_service.create_memo_item(board_id, request)
        
        # 메모 아이템 생성 후 보드 분석 트리거
        if response.success:
            background_tasks.add_task(
                board_sync_service.trigger_board_analysis,
                board_id,
                False  # force_refresh=False
            )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Memo item creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"메모 아이템 생성 실패: {str(e)}")