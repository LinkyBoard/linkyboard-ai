"""Users 도메인 모듈

Spring Boot 서버와의 사용자 동기화를 위한 도메인입니다.

구조:
    - models.py: SQLAlchemy 모델 정의 (User)
    - schemas.py: Pydantic 스키마 (UserSync, UserResponse, etc.)
    - repository.py: 데이터 접근 계층
    - service.py: 비즈니스 로직 (동기화, Upsert)
    - router.py: API 엔드포인트 (API Key 인증 포함)
    - exceptions.py: 도메인 예외
"""

from app.domains.users.exceptions import (
    UserAlreadyDeletedException,
    UserErrorCode,
    UserNotFoundException,
)
from app.domains.users.models import User
from app.domains.users.router import router
from app.domains.users.schemas import (
    BulkSyncResponse,
    UserBulkSync,
    UserResponse,
    UserSync,
)
from app.domains.users.service import UserService

__all__ = [
    "User",
    "UserService",
    "UserSync",
    "UserBulkSync",
    "UserResponse",
    "BulkSyncResponse",
    "router",
    "UserErrorCode",
    "UserNotFoundException",
    "UserAlreadyDeletedException",
]
