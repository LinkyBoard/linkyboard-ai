"""
Board Management System Integration Tests
보드 관리 시스템 통합 테스트
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from unittest.mock import patch, AsyncMock
import json
from datetime import datetime

from app.main import app
from app.core.models import Board, BoardItem, BoardAnalytics, Item, User
from app.core.database import AsyncSessionLocal


class TestBoardManagementSystem:
    """Given-When-Then 형식의 보드 관리 시스템 테스트"""

    async def given_test_data_exists(self, session: AsyncSession):
        """테스트 데이터 생성"""
        # 테스트 사용자 생성
        user = User(id=1, username="testuser", email="test@example.com")
        session.add(user)
        
        # 테스트 아이템들 생성
        items = [
            Item(
                id=1,
                title="AI 기술 동향",
                summary="인공지능 기술의 최신 동향을 다룬 아티클",
                content="AI 기술이 빠르게 발전하고 있습니다...",
                source_url="https://example.com/ai-trends",
                tags=["AI", "기술", "트렌드"],
                categories={"technology": 0.9, "ai": 0.8}
            ),
            Item(
                id=2,
                title="머신러닝 실무",
                summary="실무에서 활용하는 머신러닝 기법들",
                content="머신러닝을 실무에 적용할 때 고려사항...",
                source_url="https://example.com/ml-practice",
                tags=["머신러닝", "실무", "데이터"],
                categories={"technology": 0.8, "ml": 0.9}
            ),
            Item(
                id=3,
                title="딥러닝 프레임워크",
                summary="주요 딥러닝 프레임워크 비교",
                content="TensorFlow, PyTorch 등의 특징...",
                source_url="https://example.com/dl-frameworks",
                tags=["딥러닝", "프레임워크", "개발"],
                categories={"technology": 0.9, "development": 0.7}
            )
        ]
        
        for item in items:
            session.add(item)
        
        await session.commit()
        return {"user": user, "items": items}

    async def given_board_exists(self, session: AsyncSession, test_data: dict):
        """테스트 보드 생성"""
        board = Board(
            id=100,
            user_id=test_data["user"].id,
            title="AI 학습 자료",
            description="인공지능 학습을 위한 자료 모음",
            board_type="collection",
            visibility="private",
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        session.add(board)
        await session.commit()
        return board

    @pytest.mark.asyncio
    async def test_given_new_board_when_sync_called_then_board_created(self):
        """Given: 새로운 보드 정보 / When: 동기화 API 호출 / Then: 보드가 생성됨"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Given: 새로운 보드 동기화 요청 데이터
            board_sync_data = {
                "board_id": 101,
                "user_id": 1,
                "title": "새로운 AI 보드",
                "description": "AI 관련 새로운 자료 모음",
                "board_type": "collection",
                "visibility": "private",
                "is_active": True,
                "created_at": "2025-08-19T10:00:00Z",
                "updated_at": "2025-08-19T10:00:00Z"
            }
            
            # When: 보드 동기화 API 호출
            response = await ac.post("/v1/boards/sync", json=board_sync_data)
            
            # Then: 성공 응답 확인
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["board_id"] == 101
            assert data["message"] == "Board created successfully"
            assert data["analytics_triggered"] is True
            
            # 데이터베이스에 보드가 생성되었는지 확인
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Board).where(Board.id == 101))
                board = result.scalar_one_or_none()
                assert board is not None
                assert board.title == "새로운 AI 보드"
                assert board.user_id == 1
                assert board.is_active is True

    @pytest.mark.asyncio
    async def test_given_existing_board_when_items_synced_then_relationships_updated(self):
        """Given: 기존 보드 / When: 아이템 동기화 / Then: 보드-아이템 관계 업데이트됨"""
        async with AsyncSessionLocal() as session:
            # Given: 테스트 데이터와 보드 생성
            test_data = await self.given_test_data_exists(session)
            board = await self.given_board_exists(session, test_data)
            
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Given: 보드 아이템 동기화 요청 데이터
            items_sync_data = {
                "board_id": board.id,
                "item_ids": [1, 2, 3],
                "item_orders": {"1": 0, "2": 1, "3": 2},
                "item_contexts": {
                    "1": "AI 기초 이론",
                    "2": "실무 적용 사례",
                    "3": "개발 도구 가이드"
                }
            }
            
            # When: 아이템 동기화 API 호출
            response = await ac.post(f"/v1/boards/{board.id}/items/sync", json=items_sync_data)
            
            # Then: 성공 응답 확인
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["board_id"] == board.id
            assert data["synced_items"] == 3
            assert data["analytics_triggered"] is True
            
            # 보드-아이템 관계가 생성되었는지 확인
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(BoardItem).where(BoardItem.board_id == board.id).order_by(BoardItem.display_order)
                )
                board_items = result.scalars().all()
                assert len(board_items) == 3
                
                # 순서와 컨텍스트 확인
                assert board_items[0].item_id == 1
                assert board_items[0].display_order == 0
                assert board_items[0].item_context == "AI 기초 이론"
                
                assert board_items[1].item_id == 2
                assert board_items[1].display_order == 1
                assert board_items[1].item_context == "실무 적용 사례"

    @patch('app.ai.providers.openai_provider.OpenAIProvider.generate_completion')
    @patch('app.ai.providers.openai_provider.OpenAIProvider.create_embeddings')
    @pytest.mark.asyncio
    async def test_given_board_with_items_when_analysis_triggered_then_analytics_generated(self, mock_embeddings, mock_completion):
        """Given: 아이템이 있는 보드 / When: 분석 트리거 / Then: 분석 결과 생성됨"""
        
        # Mock AI responses
        mock_completion.return_value = "이 보드는 AI와 머신러닝 관련 자료를 종합적으로 다루고 있으며, 기초 이론부터 실무 적용까지 포괄적인 내용을 제공합니다."
        mock_embeddings.return_value = [[0.1] * 1536, [0.2] * 1536, [0.15] * 1536, [0.18] * 1536]
        
        async with AsyncSessionLocal() as session:
            # Given: 테스트 데이터, 보드, 아이템 관계 생성
            test_data = await self.given_test_data_exists(session)
            board = await self.given_board_exists(session, test_data)
            
            # 보드-아이템 관계 생성
            for i, item in enumerate(test_data["items"]):
                board_item = BoardItem(
                    board_id=board.id,
                    item_id=item.id,
                    display_order=i,
                    item_context=f"테스트 컨텍스트 {i+1}"
                )
                session.add(board_item)
            await session.commit()
            
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # When: 보드 분석 트리거
            analysis_data = {
                "board_id": board.id,
                "force_refresh": True
            }
            response = await ac.post(f"/v1/boards/{board.id}/analyze", json=analysis_data)
            
            # Then: 분석 트리거 성공 확인
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["board_id"] == board.id
            assert data["force_refresh"] is True
            
            # 잠시 대기 (백그라운드 분석 완료)
            import asyncio
            await asyncio.sleep(1)
            
            # 분석 결과 조회
            analytics_response = await ac.get(f"/v1/boards/{board.id}/analytics")
            assert analytics_response.status_code == 200
            
            analytics_data = analytics_response.json()
            assert analytics_data["board_id"] == board.id
            assert analytics_data["total_items"] == 3
            assert "content_summary" in analytics_data
            assert isinstance(analytics_data["dominant_categories"], dict)
            assert isinstance(analytics_data["tag_distribution"], dict)

    @patch('app.ai.providers.openai_provider.OpenAIProvider.create_embeddings')
    @pytest.mark.asyncio  
    async def test_given_analyzed_board_when_insights_requested_then_insights_provided(self, mock_embeddings):
        """Given: 분석된 보드 / When: 인사이트 요청 / Then: 인사이트 제공됨"""
        
        mock_embeddings.return_value = [[0.1] * 1536]
        
        async with AsyncSessionLocal() as session:
            # Given: 테스트 데이터와 보드 생성
            test_data = await self.given_test_data_exists(session)
            board = await self.given_board_exists(session, test_data)
            
            # 분석 데이터 직접 생성
            analytics = BoardAnalytics(
                board_id=board.id,
                content_summary="AI 기술 전반을 다루는 종합적인 자료 모음",
                dominant_categories={"technology": 5, "ai": 3, "ml": 2},
                tag_distribution={"AI": 0.4, "기술": 0.3, "머신러닝": 0.3},
                total_items=3,
                total_content_length=500,
                avg_item_relevance=0.75,
                content_diversity_score=0.6,
                topic_coherence_score=0.8,
                topic_embedding=[0.1] * 1536,
                analytics_version="1.0",
                last_analyzed_at=datetime.now(),
                is_stale=False
            )
            session.add(analytics)
            await session.commit()
            
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # When: 인사이트 요청
            response = await ac.get(f"/v1/boards/{board.id}/insights")
            
            # Then: 인사이트 제공됨
            assert response.status_code == 200
            insights = response.json()
            
            assert insights["board_id"] == board.id
            assert "content_quality" in insights
            assert "organization_suggestions" in insights
            assert "content_gaps" in insights
            assert "engagement_potential" in insights
            
            # 품질 평가 확인
            quality = insights["content_quality"]
            assert "score" in quality
            assert "level" in quality
            assert "coherence" in quality
            assert "diversity" in quality
            assert "relevance" in quality

    @patch('app.board_analytics.service.board_analytics_service.get_board_insights')
    @pytest.mark.asyncio
    async def test_given_board_insights_when_recommendations_requested_then_ai_suggestions_provided(self, mock_insights):
        """Given: 보드 인사이트 / When: 추천 요청 / Then: AI 추천 제공됨"""
        
        # Mock insights data
        mock_insights.return_value = {
            "board_id": 100,
            "content_quality": {"score": 0.6, "level": "보통"},
            "organization_suggestions": ["유사한 카테고리들을 그룹핑하여 정리해보세요."],
            "content_gaps": ["실습 예제나 코드 샘플이 부족합니다."],
            "engagement_potential": {"score": 0.7, "level": "높음"}
        }
        
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # When: 콘텐츠 부족 영역 추천 요청
            response = await ac.get("/board-ai/100/recommendations?user_id=1&recommendation_type=content_gaps")
            
            # Then: 추천 제공됨
            assert response.status_code == 200
            recommendations = response.json()
            
            assert recommendations["board_id"] == 100
            assert recommendations["recommendation_type"] == "content_gaps"
            assert len(recommendations["recommendations"]) > 0
            
            # 추천 내용 확인
            rec = recommendations["recommendations"][0]
            assert rec["type"] == "content_improvement"
            assert rec["priority"] in ["low", "medium", "high"]
            assert "suggestion" in rec
            assert "action" in rec
            
            # 인사이트 요약 확인
            assert "insights_summary" in recommendations
            assert "content_quality" in recommendations["insights_summary"]
            assert "engagement_potential" in recommendations["insights_summary"]

    @pytest.mark.asyncio
    async def test_given_user_boards_when_list_requested_then_boards_returned(self):
        """Given: 사용자 보드들 / When: 목록 요청 / Then: 보드 목록 반환됨"""
        
        async with AsyncSessionLocal() as session:
            # Given: 테스트 사용자와 여러 보드 생성
            user = User(id=2, username="testuser2", email="test2@example.com")
            session.add(user)
            
            boards = [
                Board(
                    id=201, user_id=2, title="AI 보드 1", description="첫 번째 AI 보드",
                    is_active=True, created_at=datetime.now(), updated_at=datetime.now()
                ),
                Board(
                    id=202, user_id=2, title="ML 보드", description="머신러닝 보드",
                    is_active=True, created_at=datetime.now(), updated_at=datetime.now()
                ),
                Board(
                    id=203, user_id=2, title="비활성 보드", description="비활성화된 보드",
                    is_active=False, created_at=datetime.now(), updated_at=datetime.now()
                )
            ]
            
            for board in boards:
                session.add(board)
            await session.commit()
            
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # When: 활성 보드만 요청
            response = await ac.get("/v1/boards/user/2")
            
            # Then: 활성 보드 목록만 반환됨
            assert response.status_code == 200
            data = response.json()
            
            assert data["total_count"] == 2  # 활성 보드만
            assert data["analyzed_count"] == 0  # 분석된 보드 없음
            assert len(data["boards"]) == 2
            
            # 제목으로 확인
            board_titles = [board["title"] for board in data["boards"]]
            assert "AI 보드 1" in board_titles
            assert "ML 보드" in board_titles
            assert "비활성 보드" not in board_titles
            
            # When: 비활성 보드 포함 요청
            response_all = await ac.get("/v1/boards/user/2?include_inactive=true")
            
            # Then: 모든 보드 반환됨
            assert response_all.status_code == 200
            data_all = response_all.json()
            
            assert data_all["total_count"] == 3  # 모든 보드
            assert len(data_all["boards"]) == 3

    @pytest.mark.asyncio
    async def test_given_board_when_deleted_then_deactivated(self):
        """Given: 활성 보드 / When: 삭제 요청 / Then: 비활성화됨"""
        
        async with AsyncSessionLocal() as session:
            # Given: 테스트 사용자와 보드 생성
            user = User(id=3, username="testuser3", email="test3@example.com")
            board = Board(
                id=301, user_id=3, title="삭제될 보드", description="삭제 테스트용 보드",
                is_active=True, created_at=datetime.now(), updated_at=datetime.now()
            )
            session.add(user)
            session.add(board)
            await session.commit()
            
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # When: 보드 삭제 요청
            delete_data = {
                "board_id": 301,
                "user_id": 3
            }
            response = await ac.delete("/v1/boards/301", json=delete_data)
            
            # Then: 삭제(비활성화) 성공
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert data["board_id"] == 301
            assert data["message"] == "Board deactivated successfully"
            assert data["analytics_triggered"] is False
            
            # 보드가 비활성화되었는지 확인
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(Board).where(Board.id == 301))
                board = result.scalar_one()
                assert board.is_active is False

    @pytest.fixture(autouse=True)
    async def cleanup_test_data(self):
        """각 테스트 후 데이터 정리"""
        yield
        
        async with AsyncSessionLocal() as session:
            # 테스트 데이터 정리
            await session.execute(delete(BoardAnalytics))
            await session.execute(delete(BoardItem))
            await session.execute(delete(Board))
            await session.execute(delete(Item))
            await session.execute(delete(User))
            await session.commit()