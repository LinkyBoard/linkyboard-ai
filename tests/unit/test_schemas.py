"""스키마 단위 테스트"""

from app.core.schemas import (
    APIResponse,
    ErrorDetail,
    ErrorResponse,
    ListAPIResponse,
    PageMeta,
)


class TestAPIResponse:
    """APIResponse 테스트"""

    def test_success_response_with_data(self):
        """데이터가 있는 성공 응답"""
        response = APIResponse(
            success=True,
            data={"id": 1, "name": "test"},
            message="조회 성공",
        )

        assert response.success is True
        assert response.message == "조회 성공"
        assert response.data == {"id": 1, "name": "test"}

    def test_success_response_without_data(self):
        """데이터가 없는 성공 응답"""
        response = APIResponse(success=True, message="삭제 성공")

        assert response.success is True
        assert response.message == "삭제 성공"
        assert response.data is None

    def test_default_message(self):
        """기본 메시지"""
        response = APIResponse(success=True)

        assert response.message == "요청이 성공적으로 처리되었습니다."


class TestListAPIResponse:
    """ListAPIResponse 테스트"""

    def test_list_response_with_pagination(self):
        """페이지네이션 메타 정보 검증"""
        items = [{"id": 1}, {"id": 2}, {"id": 3}]
        meta = PageMeta(
            total=100,
            page=2,
            size=20,
            total_pages=5,
            has_next=True,
            has_prev=True,
        )
        response = ListAPIResponse(
            success=True,
            data=items,
            meta=meta,
            message="목록 조회 성공",
        )

        assert response.success is True
        assert response.message == "목록 조회 성공"
        assert response.data == items
        assert response.meta.total == 100
        assert response.meta.page == 2
        assert response.meta.size == 20
        assert response.meta.total_pages == 5
        assert response.meta.has_next is True
        assert response.meta.has_prev is True

    def test_first_page_has_no_prev(self):
        """첫 페이지는 has_prev가 False"""
        meta = PageMeta(
            total=50,
            page=1,
            size=20,
            total_pages=3,
            has_next=True,
            has_prev=False,
        )
        response = ListAPIResponse(
            success=True,
            data=[],
            meta=meta,
        )

        assert response.meta.has_prev is False
        assert response.meta.has_next is True

    def test_last_page_has_no_next(self):
        """마지막 페이지는 has_next가 False"""
        meta = PageMeta(
            total=50,
            page=3,
            size=20,
            total_pages=3,
            has_next=False,
            has_prev=True,
        )
        response = ListAPIResponse(
            success=True,
            data=[],
            meta=meta,
        )

        assert response.meta.has_next is False
        assert response.meta.has_prev is True

    def test_empty_result(self):
        """빈 결과"""
        meta = PageMeta(
            total=0,
            page=1,
            size=20,
            total_pages=0,
            has_next=False,
            has_prev=False,
        )
        response = ListAPIResponse(
            success=True,
            data=[],
            meta=meta,
        )

        assert response.data == []
        assert response.meta.total == 0
        assert response.meta.total_pages == 0
        assert response.meta.has_next is False
        assert response.meta.has_prev is False


class TestErrorResponse:
    """ErrorResponse 테스트"""

    def test_error_response_structure(self):
        """에러 응답 구조 검증"""
        error = ErrorResponse(
            message="사용자를 찾을 수 없습니다.",
            error=ErrorDetail(
                code="USER_NOT_FOUND",
                message="사용자를 찾을 수 없습니다.",
                detail={"user_id": 123},
            ),
        )

        assert error.success is False
        assert error.message == "사용자를 찾을 수 없습니다."
        assert error.error.code == "USER_NOT_FOUND"
        assert error.error.detail == {"user_id": 123}
