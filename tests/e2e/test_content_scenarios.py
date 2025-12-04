"""콘텐츠 시나리오 E2E 테스트

이 모듈은 실제 사용자 콘텐츠 관리 시나리오를 시뮬레이션하여
전체 플로우가 올바르게 동작하는지 검증합니다.
"""

import io
import json

import pytest


class TestWebpageLifecycle:
    """웹페이지 콘텐츠 전체 생명주기 시나리오"""

    @pytest.mark.asyncio
    async def test_webpage_full_lifecycle(
        self, client, api_key_header, user_id_factory
    ):
        """웹페이지 콘텐츠 전체 생명주기 테스트

        시나리오:
        1. 웹페이지 동기화 (생성)
        2. 콘텐츠 조회
        3. 동일 URL 재동기화 (업데이트)
        4. 목록에서 확인
        5. 콘텐츠 삭제
        6. 삭제 후 목록 확인
        """
        # 1. 웹페이지 동기화
        user_id = user_id_factory()
        content_id = user_id + 10000
        url = f"https://example.com/webpage-lifecycle-{user_id}"

        response = await client.post(
            "/api/v1/contents/webpage/sync",
            json={
                "content_id": content_id,
                "user_id": user_id,
                "url": url,
                "content_hash": "a" * 64,
                "title": "Original Title",
                "tags": ["tag1", "tag2"],
            },
            headers=api_key_header,
        )
        assert response.status_code == 201
        assert response.json()["data"]["content_id"] == content_id

        # 2. 콘텐츠 조회
        response = await client.get(
            f"/api/v1/contents/{content_id}?user_id={user_id}",
            headers=api_key_header,
        )
        assert response.status_code == 200
        content = response.json()["data"]
        assert content["title"] == "Original Title"
        assert content["content_type"] == "webpage"
        assert content["summary_status"] == "pending"
        assert content["embedding_status"] == "pending"

        # 3. 동일 URL 재동기화 (업데이트)
        response = await client.post(
            "/api/v1/contents/webpage/sync",
            json={
                "content_id": content_id,
                "user_id": user_id,
                "url": url,
                "content_hash": "a" * 64,
                "title": "Updated Title",
                "tags": ["tag1", "tag2", "tag3"],
            },
            headers=api_key_header,
        )
        assert response.status_code == 201

        # 3-1. 업데이트 확인
        response = await client.get(
            f"/api/v1/contents/{content_id}?user_id={user_id}",
            headers=api_key_header,
        )
        assert response.status_code == 200
        updated_content = response.json()["data"]
        assert updated_content["title"] == "Updated Title"
        assert len(updated_content["tags"]) == 3

        # 4. 목록에서 확인
        response = await client.get(
            f"/api/v1/contents/?user_id={user_id}",
            headers=api_key_header,
        )
        assert response.status_code == 200
        contents = response.json()["data"]
        assert any(c["id"] == content_id for c in contents)

        # 5. 콘텐츠 삭제
        response = await client.request(
            method="DELETE",
            url="/api/v1/contents/",
            content=json.dumps(
                {"content_ids": [content_id], "user_id": user_id}
            ),
            headers={**api_key_header, "Content-Type": "application/json"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["deleted_count"] == 1

        # 6. 삭제 후 목록 확인 (soft delete이므로 나타나지 않음)
        response = await client.get(
            f"/api/v1/contents/?user_id={user_id}",
            headers=api_key_header,
        )
        assert response.status_code == 200
        contents = response.json()["data"]
        assert not any(c["id"] == content_id for c in contents)


class TestPDFUploadScenario:
    """PDF 업로드 시나리오"""

    @pytest.mark.asyncio
    async def test_pdf_upload_full_flow(
        self, client, api_key_header, user_id_factory
    ):
        """PDF 업로드 전체 플로우 테스트

        시나리오:
        1. PDF 업로드 및 동기화
        2. 콘텐츠 조회 (file_hash 확인)
        3. 동일 파일 재업로드 (중복 처리)
        4. 목록 조회
        """
        # 1. PDF 업로드
        user_id = user_id_factory()
        content_id = user_id + 20000
        pdf_content = b"test pdf content for e2e scenario"

        files = {
            "file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")
        }
        data = {
            "content_id": str(content_id),
            "user_id": str(user_id),
            "title": "E2E Test PDF",
            "summary": "Test summary",
            "category": "research",
        }
        response = await client.post(
            "/api/v1/contents/pdf/sync",
            files=files,
            data=data,
            headers=api_key_header,
        )
        assert response.status_code == 201
        file_hash = response.json()["data"]["file_hash"]
        assert file_hash is not None

        # 2. 콘텐츠 조회
        response = await client.get(
            f"/api/v1/contents/{content_id}?user_id={user_id}",
            headers=api_key_header,
        )
        assert response.status_code == 200
        content = response.json()["data"]
        assert content["content_type"] == "pdf"
        assert content["file_hash"] == file_hash

        # 3. 동일 파일 재업로드 (메타데이터 업데이트)
        files2 = {
            "file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")
        }
        data2 = {
            "content_id": str(content_id),
            "user_id": str(user_id),
            "title": "Updated PDF Title",
            "summary": "Updated summary",
            "category": "science",
        }
        response = await client.post(
            "/api/v1/contents/pdf/sync",
            files=files2,
            data=data2,
            headers=api_key_header,
        )
        assert response.status_code == 201
        assert response.json()["data"]["file_hash"] == file_hash  # 동일 해시

        # 4. 목록 조회
        response = await client.get(
            f"/api/v1/contents/?user_id={user_id}&content_type=pdf",
            headers=api_key_header,
        )
        assert response.status_code == 200
        contents = response.json()["data"]
        assert any(c["id"] == content_id for c in contents)


class TestMultiContentTypeScenario:
    """다양한 콘텐츠 타입 혼합 시나리오"""

    @pytest.mark.asyncio
    async def test_mixed_content_types(
        self, client, api_key_header, user_id_factory
    ):
        """여러 타입의 콘텐츠 생성 및 필터링 시나리오

        시나리오:
        1. 웹페이지 2개 생성
        2. YouTube 2개 생성
        3. PDF 1개 생성
        4. 전체 목록 조회
        5. 타입별 필터링 조회
        """
        user_id = user_id_factory()
        created_ids = []

        # 1. 웹페이지 2개 생성
        for i in range(2):
            content_id = user_id + 30000 + i
            response = await client.post(
                "/api/v1/contents/webpage/sync",
                json={
                    "content_id": content_id,
                    "user_id": user_id,
                    "url": f"https://example.com/webpage-{user_id}-{i}",
                    "content_hash": f"{'b' * 63}{i}",
                    "title": f"Webpage {i}",
                },
                headers=api_key_header,
            )
            assert response.status_code == 201
            created_ids.append(content_id)

        # 2. YouTube 2개 생성
        for i in range(2):
            content_id = user_id + 30100 + i
            response = await client.post(
                "/api/v1/contents/youtube/sync",
                json={
                    "content_id": content_id,
                    "user_id": user_id,
                    "url": f"https://youtube.com/watch?v=test{i}",
                    "content_hash": f"{'c' * 63}{i}",
                    "title": f"Video {i}",
                },
                headers=api_key_header,
            )
            assert response.status_code == 201
            created_ids.append(content_id)

        # 3. PDF 1개 생성
        content_id = user_id + 30200
        files = {
            "file": (
                "mixed.pdf",
                io.BytesIO(b"pdf for mixed scenario"),
                "application/pdf",
            )
        }
        data = {
            "content_id": str(content_id),
            "user_id": str(user_id),
            "title": "PDF Document",
        }
        response = await client.post(
            "/api/v1/contents/pdf/sync",
            files=files,
            data=data,
            headers=api_key_header,
        )
        assert response.status_code == 201
        created_ids.append(content_id)

        # 4. 전체 목록 조회
        response = await client.get(
            f"/api/v1/contents/?user_id={user_id}&size=10",
            headers=api_key_header,
        )
        assert response.status_code == 200
        all_contents = response.json()["data"]
        assert len(all_contents) >= 5

        # 5. 타입별 필터링 조회
        # 웹페이지만
        response = await client.get(
            f"/api/v1/contents/?user_id={user_id}&content_type=webpage",
            headers=api_key_header,
        )
        assert response.status_code == 200
        webpage_contents = response.json()["data"]
        assert all(c["content_type"] == "webpage" for c in webpage_contents)

        # YouTube만
        response = await client.get(
            f"/api/v1/contents/?user_id={user_id}&content_type=youtube",
            headers=api_key_header,
        )
        assert response.status_code == 200
        youtube_contents = response.json()["data"]
        assert all(c["content_type"] == "youtube" for c in youtube_contents)


class TestBulkDeleteScenario:
    """벌크 삭제 시나리오"""

    @pytest.mark.asyncio
    async def test_bulk_delete_flow(
        self, client, api_key_header, user_id_factory
    ):
        """벌크 삭제 플로우 테스트

        시나리오:
        1. 10개 콘텐츠 생성
        2. 목록 조회로 확인
        3. 5개 벌크 삭제
        4. 삭제 결과 확인
        5. 목록 조회로 남은 5개 확인
        """
        user_id = user_id_factory()
        content_ids = []

        # 1. 10개 콘텐츠 생성
        for i in range(10):
            content_id = user_id + 40000 + i
            response = await client.post(
                "/api/v1/contents/webpage/sync",
                json={
                    "content_id": content_id,
                    "user_id": user_id,
                    "url": f"https://example.com/bulk-delete-{user_id}-{i}",
                    "content_hash": f"{'d' * 63}{i % 10}",
                    "title": f"Content {i}",
                },
                headers=api_key_header,
            )
            assert response.status_code == 201
            content_ids.append(content_id)

        # 2. 목록 조회
        response = await client.get(
            f"/api/v1/contents/?user_id={user_id}&size=20",
            headers=api_key_header,
        )
        assert response.status_code == 200
        contents = response.json()["data"]
        assert len([c for c in contents if c["id"] in content_ids]) == 10

        # 3. 5개 벌크 삭제
        ids_to_delete = content_ids[:5]
        response = await client.request(
            method="DELETE",
            url="/api/v1/contents/",
            content=json.dumps(
                {"content_ids": ids_to_delete, "user_id": user_id}
            ),
            headers={**api_key_header, "Content-Type": "application/json"},
        )
        assert response.status_code == 200
        delete_result = response.json()["data"]
        assert delete_result["deleted_count"] == 5
        assert delete_result["total_requested"] == 5

        # 4. 목록 조회로 남은 5개 확인
        response = await client.get(
            f"/api/v1/contents/?user_id={user_id}&size=20",
            headers=api_key_header,
        )
        assert response.status_code == 200
        remaining_contents = response.json()["data"]
        remaining_ids = [
            c["id"] for c in remaining_contents if c["id"] in content_ids
        ]
        assert len(remaining_ids) == 5
        # 삭제되지 않은 ID들만 남아있는지 확인
        for cid in content_ids[5:]:
            assert cid in remaining_ids


class TestContentAccessControl:
    """콘텐츠 접근 제어 시나리오"""

    @pytest.mark.asyncio
    async def test_user_isolation(
        self, client, api_key_header, user_id_factory
    ):
        """사용자 간 콘텐츠 격리 테스트

        시나리오:
        1. User A가 콘텐츠 생성
        2. User B가 User A의 콘텐츠 조회 시도 → 실패
        3. User B가 자신의 콘텐츠 생성
        4. User B가 자신의 콘텐츠 조회 → 성공
        """
        user_a = user_id_factory()
        user_b = user_id_factory()

        # 1. User A가 콘텐츠 생성
        content_id_a = user_a + 50000
        response = await client.post(
            "/api/v1/contents/webpage/sync",
            json={
                "content_id": content_id_a,
                "user_id": user_a,
                "url": f"https://example.com/user-a-{user_a}",
                "content_hash": "e" * 64,
                "title": "User A Content",
            },
            headers=api_key_header,
        )
        assert response.status_code == 201

        # 2. User B가 User A의 콘텐츠 조회 시도
        response = await client.get(
            f"/api/v1/contents/{content_id_a}?user_id={user_b}",
            headers=api_key_header,
        )
        assert response.status_code == 403  # Forbidden

        # 3. User B가 자신의 콘텐츠 생성
        content_id_b = user_b + 50000
        response = await client.post(
            "/api/v1/contents/webpage/sync",
            json={
                "content_id": content_id_b,
                "user_id": user_b,
                "url": f"https://example.com/user-b-{user_b}",
                "content_hash": "f" * 64,
                "title": "User B Content",
            },
            headers=api_key_header,
        )
        assert response.status_code == 201

        # 4. User B가 자신의 콘텐츠 조회 → 성공
        response = await client.get(
            f"/api/v1/contents/{content_id_b}?user_id={user_b}",
            headers=api_key_header,
        )
        assert response.status_code == 200
        content = response.json()["data"]
        assert content["user_id"] == user_b
        assert content["title"] == "User B Content"
