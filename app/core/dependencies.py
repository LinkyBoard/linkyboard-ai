"""공통 의존성 함수 정의

이 모듈은 FastAPI 엔드포인트에서 사용되는 공통 의존성 함수들을 정의합니다.
"""

from fastapi import Header

from app.core.config import settings
from app.core.exceptions import UnauthorizedException


async def verify_internal_api_key(
    x_internal_api_key: str = Header(..., alias="X-Internal-Api-Key")
) -> None:
    """내부 API Key 검증 (Spring Boot 서버 통신용)

    Args:
        x_internal_api_key: 요청 헤더의 X-Internal-Api-Key 값

    Raises:
        UnauthorizedException: API Key가 유효하지 않은 경우

    Example:
        @router.get("/users", dependencies=[Depends(verify_internal_api_key)])
        async def get_users():
            ...
    """
    if x_internal_api_key != settings.internal_api_key:
        raise UnauthorizedException(
            message="유효하지 않은 API 키입니다.",
            error_code="INVALID_API_KEY",
        )
