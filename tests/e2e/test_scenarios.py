"""사용자 시나리오 E2E 테스트

이 모듈은 실제 사용자 시나리오를 시뮬레이션하여
전체 플로우가 올바르게 동작하는지 검증합니다.

Note:
    DB 연동이 필요한 테스트는 Docker Compose 환경에서 실행하거나
    테스트용 DB fixture를 설정한 후 진행해야 합니다.
"""

import pytest


class TestRequestTracking:
    """요청 추적 E2E 시나리오 테스트"""

    @pytest.mark.asyncio
    async def test_request_id_consistency(self, client):
        """동일 요청에 대한 Request ID 일관성"""
        custom_id = "test-request-tracking-001"

        response = await client.get(
            "/api/v1/",
            headers={"X-Request-ID": custom_id},
        )

        assert response.headers["x-request-id"] == custom_id

    @pytest.mark.asyncio
    async def test_multiple_requests_different_ids(self, client):
        """다중 요청에 대한 고유 Request ID"""
        response1 = await client.get("/api/v1/")
        response2 = await client.get("/api/v1/")

        id1 = response1.headers["x-request-id"]
        id2 = response2.headers["x-request-id"]

        assert id1 != id2


class TestAPIVersioning:
    """API 버저닝 E2E 테스트"""

    @pytest.mark.asyncio
    async def test_v1_api_accessible(self, client):
        """v1 API 접근 가능 여부"""
        response = await client.get("/api/v1/")

        assert response.status_code == 200
        # version 필드 존재 확인
        assert "version" in response.json()["data"]

    @pytest.mark.asyncio
    async def test_invalid_api_version_returns_404(self, client):
        """존재하지 않는 API 버전은 404"""
        response = await client.get("/api/v99/")

        assert response.status_code == 404


class TestHealthCheckScenario:
    """헬스 체크 시나리오 테스트"""

    @pytest.mark.asyncio
    async def test_health_check_always_accessible(self, client):
        """헬스 체크는 항상 접근 가능"""
        response = await client.get("/health")

        assert response.status_code == 200
        assert response.json()["data"]["status"] == "healthy"


class TestUserSyncScenarios:
    """사용자 동기화 E2E 시나리오 (DB 필요)"""

    @pytest.mark.asyncio
    async def test_user_sync_full_lifecycle(
        self, client, api_key_header, user_id_factory
    ):
        """사용자 동기화 전체 생명주기 테스트

        시나리오:
        1. Spring Boot에서 새 사용자 동기화 (생성)
        2. 동기화된 사용자 조회
        3. 동일 사용자 재동기화 (업데이트)
        4. 사용자 삭제 (Soft Delete)
        5. 삭제된 사용자 재동기화 (복구)
        6. 복구된 사용자 조회 및 검증
        """
        # 1. 새 사용자 동기화
        user_id = user_id_factory()
        response = await client.post(
            "/api/v1/users",
            json={"id": user_id},
            headers=api_key_header,
        )
        assert response.status_code == 201
        created_user = response.json()["data"]
        assert created_user["id"] == user_id
        assert created_user["deleted_at"] is None

        # 2. 동기화된 사용자 조회
        response = await client.get(
            f"/api/v1/users/{user_id}",
            headers=api_key_header,
        )
        assert response.status_code == 200
        assert response.json()["data"]["id"] == user_id

        # 3. 동일 사용자 재동기화 (업데이트)
        response = await client.post(
            "/api/v1/users",
            json={"id": user_id},
            headers=api_key_header,
        )
        assert response.status_code == 201
        # last_sync_at이 업데이트되어야 함
        updated_user = response.json()["data"]
        assert updated_user["last_sync_at"] is not None
        assert updated_user["last_sync_at"] >= created_user["last_sync_at"]

        # 4. 사용자 삭제
        response = await client.delete(
            f"/api/v1/users/{user_id}",
            headers=api_key_header,
        )
        assert response.status_code == 204

        # 5. 삭제된 사용자 재동기화 (복구)
        response = await client.post(
            "/api/v1/users",
            json={"id": user_id},
            headers=api_key_header,
        )
        assert response.status_code == 201
        restored_user = response.json()["data"]
        assert restored_user["deleted_at"] is None

        # 6. 복구된 사용자 조회
        response = await client.get(
            f"/api/v1/users/{user_id}",
            headers=api_key_header,
        )
        assert response.status_code == 200
        assert response.json()["data"]["deleted_at"] is None

    @pytest.mark.asyncio
    async def test_bulk_sync_scenario(
        self, client, api_key_header, user_id_factory
    ):
        """벌크 동기화 시나리오 테스트

        시나리오:
        1. 100명의 사용자 벌크 동기화
        2. 동기화 결과 검증
        3. 사용자 목록 조회로 확인
        """
        # 1. 100명 사용자 생성
        user_ids = user_id_factory(n=100)
        users = [{"id": uid} for uid in user_ids]

        response = await client.post(
            "/api/v1/users/bulk",
            json={"users": users},
            headers=api_key_header,
        )
        assert response.status_code == 201
        result = response.json()["data"]
        assert result["total"] == 100
        assert result["created"] == 100

        # 2. 사용자 목록 조회
        response = await client.get(
            "/api/v1/users?page=1&size=100",
            headers=api_key_header,
        )
        assert response.status_code == 200
        users_list = response.json()["data"]
        assert len(users_list) >= 100

        # 3. 재동기화 (모두 업데이트)
        response = await client.post(
            "/api/v1/users/bulk",
            json={"users": users},
            headers=api_key_header,
        )
        assert response.status_code == 201
        result = response.json()["data"]
        assert result["updated"] == 100
        assert result["created"] == 0


class TestErrorScenarios:
    """에러 처리 E2E 시나리오 (DB 필요)"""

    @pytest.mark.asyncio
    async def test_authentication_error_scenario(self, client, api_key_header):
        """인증 실패 후 재시도 시나리오

        시나리오:
        1. 잘못된 API Key로 요청 → 401
        2. 올바른 API Key로 재시도 → 성공
        """
        # 1. 잘못된 API Key
        invalid_headers = {"X-Internal-Api-Key": "invalid-key"}
        response = await client.get("/api/v1/users", headers=invalid_headers)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_API_KEY"

        # 2. 올바른 API Key로 재시도
        response = await client.get("/api/v1/users", headers=api_key_header)
        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_user_not_found_scenario(self, client, api_key_header):
        """존재하지 않는 사용자 접근 시나리오"""
        # 존재하지 않는 사용자 조회
        response = await client.get(
            "/api/v1/users/999999", headers=api_key_header
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "USER_NOT_FOUND"

        # 존재하지 않는 사용자 삭제
        response = await client.delete(
            "/api/v1/users/999999", headers=api_key_header
        )
        assert response.status_code == 404
