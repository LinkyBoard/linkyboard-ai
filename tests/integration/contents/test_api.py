"""Contents API 통합 테스트"""

import io
import json

import pytest


class TestAuthenticationRequired:
    """API Key 인증 필수 테스트"""

    @pytest.mark.asyncio
    async def test_webpage_sync_missing_api_key(self, client):
        """API Key 없이 웹페이지 동기화 요청"""
        response = await client.post(
            "/api/v1/contents/webpage/sync",
            json={
                "content_id": 1,
                "user_id": 100,
                "url": "https://example.com",
                "content_hash": "a" * 64,
                "title": "Test",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_contents_invalid_api_key(self, client):
        """잘못된 API Key로 콘텐츠 목록 조회"""
        headers = {"X-Internal-Api-Key": "invalid-key"}
        response = await client.get(
            "/api/v1/contents/?user_id=100", headers=headers
        )
        assert response.status_code == 401


class TestWebpageSyncAPI:
    """웹페이지 동기화 API 테스트"""

    @pytest.mark.asyncio
    async def test_sync_webpage_success(
        self, client, api_key_header, user_id_factory
    ):
        """웹페이지 동기화 성공"""
        # Given
        user_id = user_id_factory()
        content_id = user_id + 1000

        # When
        response = await client.post(
            "/api/v1/contents/webpage/sync",
            json={
                "content_id": content_id,
                "user_id": user_id,
                "url": "https://example.com/page1",
                "content_hash": "a" * 64,
                "title": "Test Page",
            },
            headers=api_key_header,
        )

        # Then
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["content_id"] == content_id
        assert data["data"]["file_hash"] is None

    @pytest.mark.asyncio
    async def test_sync_webpage_with_metadata(
        self, client, api_key_header, user_id_factory
    ):
        """메타데이터를 포함한 웹페이지 동기화"""
        # Given
        user_id = user_id_factory()
        content_id = user_id + 2000

        # When
        response = await client.post(
            "/api/v1/contents/webpage/sync",
            json={
                "content_id": content_id,
                "user_id": user_id,
                "url": "https://example.com/page2",
                "content_hash": "b" * 64,
                "title": "Test Page with Metadata",
                "summary": "Test summary",
                "tags": ["tag1", "tag2"],
                "category": "tech",
                "memo": "My memo",
            },
            headers=api_key_header,
        )

        # Then
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_sync_webpage_validation_error(self, client, api_key_header):
        """웹페이지 동기화 검증 실패"""
        # content_id가 0 이하
        response = await client.post(
            "/api/v1/contents/webpage/sync",
            json={
                "content_id": 0,
                "user_id": 100,
                "url": "https://example.com",
                "content_hash": "a" * 64,
                "title": "Test",
            },
            headers=api_key_header,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_sync_webpage_duplicate_url(
        self, client, api_key_header, user_id_factory
    ):
        """동일한 URL 중복 동기화 (업데이트)"""
        # Given
        user_id = user_id_factory()
        content_id = user_id + 3000
        url = f"https://example.com/unique-page-{user_id}"

        # 첫 번째 동기화
        response1 = await client.post(
            "/api/v1/contents/webpage/sync",
            json={
                "content_id": content_id,
                "user_id": user_id,
                "url": url,
                "content_hash": "c" * 64,
                "title": "Original Title",
            },
            headers=api_key_header,
        )
        assert response1.status_code == 201

        # 두 번째 동기화 (동일 URL, 다른 타이틀)
        response2 = await client.post(
            "/api/v1/contents/webpage/sync",
            json={
                "content_id": content_id,
                "user_id": user_id,
                "url": url,
                "content_hash": "c" * 64,
                "title": "Updated Title",
            },
            headers=api_key_header,
        )
        assert response2.status_code == 201


class TestYouTubeSyncAPI:
    """YouTube 동기화 API 테스트"""

    @pytest.mark.asyncio
    async def test_sync_youtube_success(
        self, client, api_key_header, user_id_factory
    ):
        """YouTube 동기화 성공"""
        # Given
        user_id = user_id_factory()
        content_id = user_id + 4000

        # When
        response = await client.post(
            "/api/v1/contents/youtube/sync",
            json={
                "content_id": content_id,
                "user_id": user_id,
                "url": "https://youtube.com/watch?v=test",
                "content_hash": "d" * 64,
                "title": "Test Video",
            },
            headers=api_key_header,
        )

        # Then
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["content_id"] == content_id


class TestPDFSyncAPI:
    """PDF 동기화 API 테스트"""

    @pytest.mark.asyncio
    async def test_sync_pdf_success(
        self, client, api_key_header, user_id_factory
    ):
        """PDF 업로드 및 동기화 성공"""
        # Given
        user_id = user_id_factory()
        content_id = user_id + 5000
        pdf_content = b"fake pdf content for testing"

        # When
        files = {
            "file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")
        }
        data = {
            "content_id": str(content_id),
            "user_id": str(user_id),
            "title": "Test PDF Document",
        }
        response = await client.post(
            "/api/v1/contents/pdf/sync",
            files=files,
            data=data,
            headers=api_key_header,
        )

        # Then
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["data"]["content_id"] == content_id
        assert response_data["data"]["file_hash"] is not None
        assert len(response_data["data"]["file_hash"]) == 64

    @pytest.mark.asyncio
    async def test_sync_pdf_with_metadata(
        self, client, api_key_header, user_id_factory
    ):
        """메타데이터를 포함한 PDF 업로드"""
        # Given
        user_id = user_id_factory()
        content_id = user_id + 6000
        pdf_content = b"fake pdf content with metadata"

        # When
        files = {
            "file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")
        }
        data = {
            "content_id": str(content_id),
            "user_id": str(user_id),
            "title": "PDF with Metadata",
            "summary": "Test summary",
            "tags": "tag1, tag2, tag3",
            "category": "research",
            "memo": "Important document",
        }
        response = await client.post(
            "/api/v1/contents/pdf/sync",
            files=files,
            data=data,
            headers=api_key_header,
        )

        # Then
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["success"] is True


class TestContentGetAPI:
    """콘텐츠 상세 조회 API 테스트"""

    @pytest.mark.asyncio
    async def test_get_content_success(
        self, client, api_key_header, user_id_factory
    ):
        """콘텐츠 상세 조회 성공"""
        # Given: 먼저 콘텐츠 생성
        user_id = user_id_factory()
        content_id = user_id + 7000
        await client.post(
            "/api/v1/contents/webpage/sync",
            json={
                "content_id": content_id,
                "user_id": user_id,
                "url": f"https://example.com/get-test-{user_id}",
                "content_hash": "e" * 64,
                "title": "Get Test Page",
            },
            headers=api_key_header,
        )

        # When
        response = await client.get(
            f"/api/v1/contents/{content_id}?user_id={user_id}",
            headers=api_key_header,
        )

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == content_id
        assert data["data"]["title"] == "Get Test Page"

    @pytest.mark.asyncio
    async def test_get_content_not_found(self, client, api_key_header):
        """존재하지 않는 콘텐츠 조회"""
        response = await client.get(
            "/api/v1/contents/999999?user_id=100",
            headers=api_key_header,
        )
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False


class TestContentListAPI:
    """콘텐츠 목록 조회 API 테스트"""

    @pytest.mark.asyncio
    async def test_list_contents_success(
        self, client, api_key_header, user_id_factory
    ):
        """콘텐츠 목록 조회 성공"""
        # Given
        user_id = user_id_factory()

        # When
        response = await client.get(
            f"/api/v1/contents/?user_id={user_id}",
            headers=api_key_header,
        )

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "meta" in data
        assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_list_contents_pagination(
        self, client, api_key_header, user_id_factory
    ):
        """콘텐츠 목록 페이지네이션 테스트"""
        # Given
        user_id = user_id_factory()

        # When
        response = await client.get(
            f"/api/v1/contents/?user_id={user_id}&page=1&size=5",
            headers=api_key_header,
        )

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["page"] == 1
        assert data["meta"]["size"] == 5

    @pytest.mark.asyncio
    async def test_list_contents_user_id_required(
        self, client, api_key_header
    ):
        """user_id 없이 목록 조회 시 422 에러"""
        response = await client.get(
            "/api/v1/contents/",
            headers=api_key_header,
        )
        assert response.status_code == 422  # FastAPI validation error


class TestContentDeleteAPI:
    """콘텐츠 삭제 API 테스트"""

    @pytest.mark.asyncio
    async def test_delete_contents_success(
        self, client, api_key_header, user_id_factory
    ):
        """콘텐츠 벌크 삭제 성공"""
        # Given: 먼저 콘텐츠 생성
        user_id = user_id_factory()
        content_ids = []
        for i in range(3):
            content_id = user_id + 8000 + i
            await client.post(
                "/api/v1/contents/webpage/sync",
                json={
                    "content_id": content_id,
                    "user_id": user_id,
                    "url": f"https://example.com/delete-test-{user_id}-{i}",
                    "content_hash": f"{'f' * 63}{i}",
                    "title": f"Delete Test {i}",
                },
                headers=api_key_header,
            )
            content_ids.append(content_id)

        # When
        response = await client.request(
            method="DELETE",
            url="/api/v1/contents/",
            content=json.dumps(
                {"content_ids": content_ids, "user_id": user_id}
            ),
            headers={**api_key_header, "Content-Type": "application/json"},
        )

        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["deleted_count"] == 3
        assert data["data"]["total_requested"] == 3

    @pytest.mark.asyncio
    async def test_delete_contents_validation_error(
        self, client, api_key_header
    ):
        """삭제 요청 검증 실패 (빈 목록)"""
        response = await client.request(
            method="DELETE",
            url="/api/v1/contents/",
            content=json.dumps({"content_ids": [], "user_id": 100}),
            headers={**api_key_header, "Content-Type": "application/json"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_delete_contents_exceeds_limit(self, client, api_key_header):
        """삭제 요청 제한 초과 (100개 이상)"""
        content_ids = list(range(1, 102))
        response = await client.request(
            method="DELETE",
            url="/api/v1/contents/",
            content=json.dumps({"content_ids": content_ids, "user_id": 100}),
            headers={**api_key_header, "Content-Type": "application/json"},
        )
        assert response.status_code == 422
