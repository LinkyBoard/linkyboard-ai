"""Users API 통합 테스트 - API 엔드포인트 및 인증 검증"""

import pytest


class TestAuthenticationRequired:
    """API Key 인증 필수 테스트"""

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_422(self, client):
        """API Key 없이 요청하면 422 반환"""
        response = await client.get("/api/v1/users")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_api_key_returns_401(self, client):
        """잘못된 API Key로 요청하면 401 반환"""
        headers = {"X-Internal-Api-Key": "invalid-key"}
        response = await client.get("/api/v1/users", headers=headers)

        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "INVALID_API_KEY"


class TestUsersListAPI:
    """사용자 목록 조회 API 테스트"""

    @pytest.mark.asyncio
    async def test_get_users_with_valid_api_key(self, client, api_key_header):
        """유효한 API Key로 사용자 목록 조회"""
        response = await client.get("/api/v1/users", headers=api_key_header)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "meta" in data
        assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_get_users_pagination_params(self, client, api_key_header):
        """페이지네이션 파라미터 테스트"""
        response = await client.get(
            "/api/v1/users?page=1&size=10", headers=api_key_header
        )

        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["page"] == 1
        assert data["meta"]["size"] == 10

    @pytest.mark.asyncio
    async def test_get_users_include_deleted_filter(
        self, client, api_key_header
    ):
        """include_deleted 필터 파라미터 테스트"""
        response = await client.get(
            "/api/v1/users?include_deleted=true", headers=api_key_header
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestUserDetailAPI:
    """사용자 상세 조회 API 테스트"""

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, client, api_key_header):
        """존재하지 않는 사용자 조회"""
        response = await client.get(
            "/api/v1/users/999999", headers=api_key_header
        )

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "USER_NOT_FOUND"


class TestUserUpsertAPI:
    """사용자 동기화 (Upsert) API 테스트"""

    @pytest.mark.asyncio
    async def test_upsert_user_validation_error(self, client, api_key_header):
        """잘못된 데이터로 사용자 동기화"""
        # ID가 0 이하인 경우
        response = await client.post(
            "/api/v1/users", json={"id": 0}, headers=api_key_header
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_upsert_user_missing_id(self, client, api_key_header):
        """ID 없이 사용자 동기화"""
        response = await client.post(
            "/api/v1/users", json={}, headers=api_key_header
        )

        assert response.status_code == 422


class TestBulkSyncAPI:
    """벌크 동기화 API 테스트"""

    @pytest.mark.asyncio
    async def test_bulk_sync_validation_empty_list(
        self, client, api_key_header
    ):
        """빈 목록으로 벌크 동기화"""
        response = await client.post(
            "/api/v1/users/bulk", json={"users": []}, headers=api_key_header
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_bulk_sync_validation_max_limit(
        self, client, api_key_header
    ):
        """최대 개수 초과 벌크 동기화"""
        # 1001개는 실패해야 함
        users = [{"id": i} for i in range(1, 1002)]
        response = await client.post(
            "/api/v1/users/bulk", json={"users": users}, headers=api_key_header
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_bulk_sync_valid_request_format(
        self, client, api_key_header
    ):
        """유효한 형식의 벌크 동기화 요청"""
        users = [{"id": 1}, {"id": 2}, {"id": 3}]
        response = await client.post(
            "/api/v1/users/bulk", json={"users": users}, headers=api_key_header
        )

        assert response.status_code == 201


class TestUserDeleteAPI:
    """사용자 삭제 API 테스트"""

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, client, api_key_header):
        """존재하지 않는 사용자 삭제"""
        response = await client.delete(
            "/api/v1/users/999999", headers=api_key_header
        )

        assert response.status_code == 404
