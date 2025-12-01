"""Users 도메인 모듈 (템플릿 예제)

이 모듈은 DDD 기반 도메인 구조의 예제입니다.
새 도메인을 추가할 때 이 구조를 참고하세요.

구조:
    - models.py: SQLAlchemy 모델 정의
    - schemas.py: Pydantic 스키마 (요청/응답)
    - repository.py: 데이터 접근 계층
    - service.py: 비즈니스 로직
    - router.py: API 엔드포인트
    - exceptions.py: 도메인 예외

새 도메인 추가 방법:
    1. app/domains/<domain_name>/ 디렉토리 생성
    2. 위 파일들을 복사하여 수정
    3. app/api/v1/__init__.py에 라우터 등록
"""

from app.domains.users.exceptions import (
    InvalidPasswordException,
    UserAlreadyExistsException,
    UserErrorCode,
    UserInactiveException,
    UsernameAlreadyExistsException,
    UserNotFoundException,
)
from app.domains.users.models import User
from app.domains.users.router import router
from app.domains.users.schemas import UserCreate, UserResponse, UserUpdate
from app.domains.users.service import UserService

__all__ = [
    "User",
    "UserService",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "router",
    "UserErrorCode",
    "UserNotFoundException",
    "UserAlreadyExistsException",
    "UsernameAlreadyExistsException",
    "UserInactiveException",
    "InvalidPasswordException",
]
