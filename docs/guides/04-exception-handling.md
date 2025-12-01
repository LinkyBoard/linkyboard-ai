# 예외 처리 규칙

## 예외 계층 구조

```
BaseAPIException (app/core/exceptions.py)
├── BadRequestException (400)
├── UnauthorizedException (401)
├── ForbiddenException (403)
├── NotFoundException (404)
├── ConflictException (409)
└── InternalServerException (500)

도메인 예외 (app/domains/*/exceptions.py)
├── UserNotFoundException (NotFoundException 상속)
├── UsernameAlreadyExistsException (ConflictException 상속)
└── ...
```

## 전역 예외 사용

```python
from app.core.exceptions import (
    NotFoundException,
    BadRequestException,
    ConflictException,
)

# 기본 메시지 사용
raise NotFoundException()  # "리소스를 찾을 수 없습니다."

# 커스텀 메시지 사용
raise NotFoundException(
    message="게시글을 찾을 수 없습니다.",
    detail={"post_id": 123},
)
```

## 도메인 예외 정의

### 에러 코드 정의

```python
# app/domains/users/exceptions.py
from enum import Enum

class UserErrorCode(str, Enum):
    """사용자 도메인 에러 코드"""

    USER_NOT_FOUND = "USER_NOT_FOUND"
    USER_ALREADY_EXISTS = "USER_ALREADY_EXISTS"
    USERNAME_ALREADY_EXISTS = "USERNAME_ALREADY_EXISTS"
    USER_INACTIVE = "USER_INACTIVE"
    INVALID_PASSWORD = "INVALID_PASSWORD"
```

### 도메인 예외 클래스

```python
from app.core.exceptions import NotFoundException, ConflictException

class UserNotFoundException(NotFoundException):
    """사용자를 찾을 수 없는 경우"""

    def __init__(self, user_id: int | str | None = None):
        detail = {"user_id": user_id} if user_id else {}
        super().__init__(
            message="사용자를 찾을 수 없습니다.",
            error_code=UserErrorCode.USER_NOT_FOUND,
            detail=detail,
        )


class UsernameAlreadyExistsException(ConflictException):
    """사용자명이 이미 존재하는 경우"""

    def __init__(self, username: str):
        super().__init__(
            message="이미 사용 중인 사용자명입니다.",
            error_code=UserErrorCode.USERNAME_ALREADY_EXISTS,
            detail={"username": username},
        )
```

## 예외 사용 예시

### Service 계층에서 발생

```python
# app/domains/users/service.py
class UserService:
    async def get_user(self, user_id: int) -> User:
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise UserNotFoundException(user_id=user_id)
        return user

    async def create_user(self, user_data: UserCreate) -> User:
        if await self.repository.exists_by_username(user_data.username):
            raise UsernameAlreadyExistsException(username=user_data.username)
        ...
```

### Router에서는 예외 처리 불필요

```python
# app/domains/users/router.py
@router.get("/{user_id}")
async def get_user(user_id: int, service: UserService = Depends()):
    # 예외는 자동으로 핸들러에서 처리됨
    user = await service.get_user(user_id)
    return create_response(data=UserResponse.model_validate(user))
```

## 예외 응답 형식

```json
{
    "success": false,
    "message": "사용자를 찾을 수 없습니다.",
    "error": {
        "code": "USER_NOT_FOUND",
        "message": "사용자를 찾을 수 없습니다.",
        "detail": {
            "user_id": 123
        }
    }
}
```

## 예외 핸들러

`app/main.py`에서 자동 등록됨:

```python
# 커스텀 API 예외
app.add_exception_handler(BaseAPIException, base_exception_handler)

# FastAPI HTTPException
app.add_exception_handler(HTTPException, http_exception_handler)

# 예상치 못한 예외 (500)
app.add_exception_handler(Exception, generic_exception_handler)
```

## 새 도메인 예외 추가 체크리스트

1. [ ] `UserErrorCode` 같은 에러 코드 Enum 정의
2. [ ] 적절한 전역 예외 클래스 상속
3. [ ] `error_code`, `message`, `detail` 설정
4. [ ] `__init__.py`에서 export
5. [ ] 테스트 작성
