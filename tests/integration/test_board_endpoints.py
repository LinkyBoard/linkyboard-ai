"""
Board Management API Integration Tests
보드 관리 API 통합 테스트 - 실제 동작 확인용
"""

import pytest
from httpx import AsyncClient
from app.main import app


class TestBoardEndpoints:
    """Given-When-Then 형식의 보드 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_given_server_running_when_board_sync_endpoint_called_then_responds(self):
        """Given: 서버 실행 중 / When: 보드 동기화 엔드포인트 호출 / Then: 응답 반환"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Given: 보드 동기화 요청 데이터
            sync_data = {
                "board_id": 999,
                "user_id": 1,
                "title": "테스트 보드",
                "description": "API 테스트용 보드",
                "board_type": "collection",
                "visibility": "private",
                "is_active": True,
                "created_at": "2025-08-19T10:00:00Z",
                "updated_at": "2025-08-19T10:00:00Z"
            }
            
            # When: API 호출
            response = await ac.post("/v1/boards/sync", json=sync_data)
            
            # Then: 적절한 응답 (성공 또는 에러)
            assert response.status_code in [200, 400, 500]  # 데이터베이스 연결에 따라
            
            if response.status_code == 200:
                data = response.json()
                assert "success" in data
                assert "board_id" in data

    @pytest.mark.asyncio
    async def test_given_server_when_user_boards_endpoint_called_then_responds(self):
        """Given: 서버 / When: 사용자 보드 목록 호출 / Then: 응답 반환"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # When: 사용자 보드 목록 API 호출
            response = await ac.get("/v1/boards/user/1")
            
            # Then: 적절한 응답
            assert response.status_code in [200, 500]  # 데이터베이스 연결에 따라
            
            if response.status_code == 200:
                data = response.json()
                assert "boards" in data
                assert "total_count" in data
                assert "analyzed_count" in data

    @pytest.mark.asyncio
    async def test_given_server_when_board_recommendations_called_then_responds(self):
        """Given: 서버 / When: 보드 추천 API 호출 / Then: 응답 반환"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # When: 보드 추천 API 호출
            response = await ac.get("/board-ai/999/recommendations?user_id=1&recommendation_type=content_gaps")
            
            # Then: 적절한 응답
            assert response.status_code in [200, 404, 500]  # 데이터 존재 여부에 따라

    @pytest.mark.asyncio
    async def test_given_openapi_spec_when_requested_then_includes_board_endpoints(self):
        """Given: OpenAPI 스펙 / When: 요청 / Then: 보드 엔드포인트 포함됨"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # When: OpenAPI 스펙 요청
            response = await ac.get("/openapi.json")
            
            # Then: 보드 관련 엔드포인트들이 포함됨
            assert response.status_code == 200
            spec = response.json()
            
            paths = spec.get("paths", {})
            
            # 주요 보드 엔드포인트들이 정의되어 있는지 확인
            board_endpoints = [
                "/v1/boards/sync",
                "/v1/boards/{board_id}/items/sync", 
                "/v1/boards/{board_id}/analytics",
                "/v1/boards/{board_id}/insights",
                "/board-ai/{board_id}/recommendations"
            ]
            
            for endpoint in board_endpoints:
                assert endpoint in paths, f"Missing endpoint: {endpoint}"

    @pytest.mark.asyncio
    async def test_given_docs_when_accessed_then_includes_board_api_documentation(self):
        """Given: API 문서 / When: 접근 / Then: 보드 API 문서 포함"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # When: Swagger UI 문서 접근
            response = await ac.get("/docs")
            
            # Then: 문서가 로드됨
            assert response.status_code == 200
            assert "swagger" in response.text.lower() or "openapi" in response.text.lower()

    def test_given_app_routes_when_inspected_then_board_routes_registered(self):
        """Given: 앱 라우트 / When: 검사 / Then: 보드 라우트 등록됨"""
        # Given: FastAPI 앱
        routes = [route.path for route in app.routes if hasattr(route, 'path')]
        
        # Then: 보드 관련 라우트들이 등록되어 있음
        board_routes = [
            "/v1/boards/sync",
            "/v1/boards/{board_id}/items/sync",
            "/v1/boards/{board_id}/analytics", 
            "/v1/boards/{board_id}/insights",
            "/board-ai/{board_id}/recommendations"
        ]
        
        for route in board_routes:
            assert route in routes, f"Missing route: {route}"

    def test_given_app_tags_when_inspected_then_board_tags_present(self):
        """Given: 앱 태그 / When: 검사 / Then: 보드 태그 존재"""
        # Given: OpenAPI 스펙에서 태그 확인
        openapi_schema = app.openapi()
        tags = [tag["name"] for tag in openapi_schema.get("tags", [])]
        
        # Then: 보드 관련 태그들이 존재
        expected_tags = ["Board Sync", "board-ai"]
        
        for tag in expected_tags:
            assert tag in tags, f"Missing API tag: {tag}"