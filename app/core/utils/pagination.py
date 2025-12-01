"""페이지네이션 유틸리티"""

from fastapi import Query


class PageParams:
    """페이지네이션 파라미터 의존성

    Example::

        from app.core.utils.pagination import PageParams
        from app.core.schemas import ListAPIResponse, create_list_response

        @router.get("", response_model=ListAPIResponse[UserResponse])
        async def get_users(page_params: PageParams = Depends()):
            users, total = await service.get_users(
                page=page_params.page,
                size=page_params.size,
            )
            return create_list_response(
                data=users,
                total=total,
                page=page_params.page,
                size=page_params.size,
            )
    """

    def __init__(
        self,
        page: int = Query(1, ge=1, description="페이지 번호"),
        size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    ):
        self.page = page
        self.size = size

    @property
    def skip(self) -> int:
        """오프셋 계산"""
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        """리미트 (size와 동일)"""
        return self.size
