"""API 통합 테스트 - 응답 구조, 로깅, 미들웨어 검증"""

import pytest


class TestHealthCheck:
    """헬스 체크 API 테스트"""

    @pytest.mark.asyncio
    async def test_health_check_response_structure(self, client):
        """헬스 체크 응답 구조 검증"""
        response = await client.get("/health")

        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["message"] == "OK"
        assert "data" in data
        assert data["data"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_has_request_id_header(self, client):
        """헬스 체크는 로깅 제외 경로 (X-Request-ID 없음)"""
        response = await client.get("/health")

        # /health는 EXCLUDE_PATHS에 있어서 헤더가 없음
        assert response.status_code == 200


class TestAPIRoot:
    """API 루트 테스트"""

    @pytest.mark.asyncio
    async def test_api_v1_root(self, client):
        """API v1 루트 응답 검증"""
        response = await client.get("/api/v1/")

        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "version" in data["data"]


class TestMiddleware:
    """미들웨어 테스트"""

    @pytest.mark.asyncio
    async def test_request_id_header_in_response(self, client):
        """응답에 X-Request-ID 헤더 포함 여부"""
        response = await client.get("/api/v1/")

        assert "x-request-id" in response.headers
        assert len(response.headers["x-request-id"]) == 36  # UUID 형식

    @pytest.mark.asyncio
    async def test_process_time_header_in_response(self, client):
        """응답에 X-Process-Time 헤더 포함 여부"""
        response = await client.get("/api/v1/")

        assert "x-process-time" in response.headers
        assert "ms" in response.headers["x-process-time"]

    @pytest.mark.asyncio
    async def test_custom_request_id_forwarded(self, client):
        """클라이언트가 보낸 X-Request-ID가 응답에 유지되는지"""
        custom_request_id = "custom-request-id-12345"
        response = await client.get(
            "/api/v1/",
            headers={"X-Request-ID": custom_request_id},
        )

        assert response.headers["x-request-id"] == custom_request_id


class TestResponseStructure:
    """API 응답 구조 테스트"""

    @pytest.mark.asyncio
    async def test_success_response_structure(self, client):
        """성공 응답 구조 검증"""
        response = await client.get("/api/v1/")

        data = response.json()

        # 필수 필드 검증
        assert "success" in data
        assert "message" in data
        assert data["success"] is True
