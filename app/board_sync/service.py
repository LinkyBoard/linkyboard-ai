"""
Board Sync Service - 보드 동기화 및 분석 서비스
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.core.models import Board, BoardItem, BoardAnalytics, Item, User
from app.core.logging import get_logger
from app.board_sync.schemas import (
    BoardSyncRequest, BoardItemSyncRequest, 
    BoardSyncResponse, BoardItemSyncResponse,
    BoardAnalyticsResponse
)

logger = get_logger(__name__)


class BoardSyncService:
    """보드 동기화 서비스"""

    async def sync_board(self, request: BoardSyncRequest) -> BoardSyncResponse:
        """
        보드 정보 동기화
        """
        try:
            async with AsyncSessionLocal() as session:
                # 기존 보드 확인
                result = await session.execute(
                    select(Board).where(Board.id == request.board_id)
                )
                existing_board = result.scalar_one_or_none()
                
                if existing_board:
                    # 기존 보드 업데이트
                    existing_board.user_id = request.user_id
                    existing_board.title = request.title
                    existing_board.description = request.description
                    existing_board.board_type = request.board_type
                    existing_board.visibility = request.visibility
                    existing_board.is_active = request.is_active
                    existing_board.last_sync_at = datetime.now()
                    existing_board.updated_at = request.updated_at or datetime.now()
                    
                    logger.info(f"Updated existing board {request.board_id}")
                    message = "Board updated successfully"
                    
                else:
                    # 새 보드 생성
                    new_board = Board(
                        id=request.board_id,
                        user_id=request.user_id,
                        title=request.title,
                        description=request.description,
                        board_type=request.board_type,
                        visibility=request.visibility,
                        is_active=request.is_active,
                        last_sync_at=datetime.now(),
                        created_at=request.created_at,
                        updated_at=request.updated_at
                    )
                    session.add(new_board)
                    
                    logger.info(f"Created new board {request.board_id}")
                    message = "Board created successfully"
                
                await session.commit()
                
                # 분석 트리거 여부 결정 (보드가 활성 상태일 때만)
                analytics_triggered = request.is_active
                
                return BoardSyncResponse(
                    success=True,
                    board_id=request.board_id,
                    message=message,
                    synced_at=datetime.now(),
                    analytics_triggered=analytics_triggered
                )
                
        except Exception as e:
            logger.error(f"Failed to sync board {request.board_id}: {str(e)}")
            raise Exception(f"보드 동기화 실패: {str(e)}")

    async def sync_board_items(self, request: BoardItemSyncRequest) -> BoardItemSyncResponse:
        """
        보드 아이템 관계 동기화
        """
        try:
            async with AsyncSessionLocal() as session:
                # 기존 보드-아이템 관계 삭제
                await session.execute(
                    delete(BoardItem).where(BoardItem.board_id == request.board_id)
                )
                
                synced_items = 0
                
                # 새로운 보드-아이템 관계 생성
                for item_id in request.item_ids:
                    # 아이템이 존재하는지 확인
                    result = await session.execute(
                        select(Item).where(Item.id == item_id)
                    )
                    item = result.scalar_one_or_none()
                    
                    if item:
                        board_item = BoardItem(
                            board_id=request.board_id,
                            item_id=item_id,
                            added_at=datetime.now()
                        )
                        session.add(board_item)
                        synced_items += 1
                    else:
                        logger.warning(f"Item {item_id} not found for board {request.board_id}")
                
                await session.commit()
                
                logger.info(f"Synced {synced_items} items for board {request.board_id}")
                
                return BoardItemSyncResponse(
                    success=True,
                    board_id=request.board_id,
                    synced_items=synced_items,
                    message=f"Successfully synced {synced_items} items",
                    synced_at=datetime.now(),
                    analytics_triggered=synced_items > 0
                )
                
        except Exception as e:
            logger.error(f"Failed to sync board items for {request.board_id}: {str(e)}")
            raise Exception(f"보드 아이템 동기화 실패: {str(e)}")

    async def delete_board(self, board_id: int, user_id: int) -> BoardSyncResponse:
        """
        보드 삭제 (비활성화)
        """
        try:
            async with AsyncSessionLocal() as session:
                # 보드 확인 및 비활성화
                result = await session.execute(
                    select(Board).where(
                        Board.id == board_id,
                        Board.user_id == user_id
                    )
                )
                board = result.scalar_one_or_none()
                
                if not board:
                    raise ValueError(f"Board {board_id} not found for user {user_id}")
                
                board.is_active = False
                board.last_sync_at = datetime.now()
                await session.commit()
                
                logger.info(f"Deactivated board {board_id}")
                
                return BoardSyncResponse(
                    success=True,
                    board_id=board_id,
                    message="Board deactivated successfully",
                    synced_at=datetime.now(),
                    analytics_triggered=False
                )
                
        except Exception as e:
            logger.error(f"Failed to delete board {board_id}: {str(e)}")
            raise Exception(f"보드 삭제 실패: {str(e)}")

    async def get_board_analytics(self, board_id: int) -> Optional[BoardAnalyticsResponse]:
        """
        보드 분석 정보 조회
        """
        try:
            async with AsyncSessionLocal() as session:
                # 보드와 분석 정보 조회
                result = await session.execute(
                    select(Board)
                    .options(selectinload(Board.board_analytics))
                    .where(Board.id == board_id)
                )
                board = result.scalar_one_or_none()
                
                if not board:
                    return None
                
                if not board.board_analytics:
                    # 분석 정보가 없으면 기본 응답 반환
                    return BoardAnalyticsResponse(
                        board_id=board_id,
                        total_items=0,
                        total_content_length=0,
                        avg_item_relevance=0.0,
                        analytics_version="1.0",
                        last_analyzed_at=datetime.now(),
                        is_stale=True
                    )
                
                analytics = board.board_analytics
                
                return BoardAnalyticsResponse(
                    board_id=board_id,
                    content_summary=analytics.content_summary,
                    dominant_categories=analytics.dominant_categories or {},
                    tag_distribution=analytics.tag_distribution or {},
                    total_items=analytics.total_items,
                    total_content_length=analytics.total_content_length,
                    avg_item_relevance=analytics.avg_item_relevance,
                    content_diversity_score=analytics.content_diversity_score,
                    topic_coherence_score=analytics.topic_coherence_score,
                    analytics_version=analytics.analytics_version,
                    last_analyzed_at=analytics.last_analyzed_at,
                    is_stale=analytics.is_stale
                )
                
        except Exception as e:
            logger.error(f"Failed to get board analytics for {board_id}: {str(e)}")
            return None

    async def get_user_boards(self, user_id: int, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """
        사용자의 보드 목록 조회
        """
        try:
            async with AsyncSessionLocal() as session:
                query = select(Board).where(Board.user_id == user_id)
                
                if not include_inactive:
                    query = query.where(Board.is_active == True)
                
                query = query.order_by(Board.updated_at.desc())
                
                result = await session.execute(query)
                boards = result.scalars().all()
                
                board_list = []
                for board in boards:
                    board_data = {
                        "board_id": board.id,
                        "title": board.title,
                        "description": board.description,
                        "board_type": board.board_type,
                        "visibility": board.visibility,
                        "is_active": board.is_active,
                        "item_count": board.item_count,
                        "is_analyzed": board.is_analyzed,
                        "created_at": board.created_at,
                        "updated_at": board.updated_at,
                        "last_sync_at": board.last_sync_at
                    }
                    board_list.append(board_data)
                
                return board_list
                
        except Exception as e:
            logger.error(f"Failed to get boards for user {user_id}: {str(e)}")
            return []

    async def trigger_board_analysis(self, board_id: int, force_refresh: bool = False) -> bool:
        """
        보드 분석 트리거 (백그라운드 작업)
        """
        try:
            from app.board_analytics.service import board_analytics_service
            
            logger.info(f"Board analysis triggered for board {board_id}, force_refresh={force_refresh}")
            
            # 분석 실행
            analytics = await board_analytics_service.analyze_board(board_id, force_refresh)
            
            if analytics:
                logger.info(f"Board analysis completed successfully for board {board_id}")
                return True
            else:
                logger.warning(f"Board analysis failed for board {board_id}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to trigger analysis for board {board_id}: {str(e)}")
            return False


# 싱글톤 서비스 인스턴스
board_sync_service = BoardSyncService()