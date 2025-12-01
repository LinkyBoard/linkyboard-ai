# 코드 작성 규칙

## 코드 스타일

### 포매터 및 린터

| 도구 | 용도 | 설정 파일 |
|------|------|----------|
| Black | 코드 포맷팅 | `pyproject.toml` |
| isort | import 정렬 | `pyproject.toml` |
| Flake8 | 린트 검사 | `.pre-commit-config.yaml` |
| mypy | 타입 체크 | `pyproject.toml` |

### 기본 규칙

- **줄 길이**: 100자
- **들여쓰기**: 스페이스 4칸
- **문자열**: 큰따옴표(`"`) 사용
- **타입 힌트**: 모든 함수에 필수

```python
# ✅ 좋은 예
def get_user(user_id: int) -> User:
    """사용자 조회"""
    ...

# ❌ 나쁜 예
def get_user(user_id):
    ...
```

## Docstring 규칙

### 모듈 docstring

```python
"""Users 도메인 서비스

이 모듈은 사용자 관련 비즈니스 로직을 담당합니다.
"""
```

### 함수/메서드 docstring

```python
def create_user(self, user_data: UserCreate) -> User:
    """사용자 생성

    Args:
        user_data: 사용자 생성 데이터

    Returns:
        생성된 사용자 객체

    Raises:
        UsernameAlreadyExistsException: 사용자명 중복 시
    """
```

### 클래스 docstring

```python
class UserService:
    """사용자 서비스

    사용자 관련 비즈니스 로직을 처리합니다.

    Attributes:
        repository: 사용자 리포지토리
    """
```

### Example 블록 (doctest 스타일 X)

```python
# ✅ 좋은 예 - Example:: 형식 사용
"""페이지네이션 파라미터

Example::

    @router.get("")
    async def get_users(page_params: PageParams = Depends()):
        ...
"""

# ❌ 나쁜 예 - >>> 형식 사용 금지
"""
Example:
    >>> @router.get("")
    >>> async def get_users():
"""
```

## 네이밍 규칙

### 파일명

| 유형 | 규칙 | 예시 |
|------|------|------|
| 모듈 | snake_case | `user_service.py` |
| 클래스 | PascalCase | `UserService` |
| 함수/변수 | snake_case | `get_user`, `user_id` |
| 상수 | UPPER_SNAKE_CASE | `MAX_PAGE_SIZE` |

### 도메인 파일

| 파일 | 내용 |
|------|------|
| `models.py` | SQLAlchemy 모델 |
| `schemas.py` | Pydantic 스키마 |
| `repository.py` | 데이터 접근 계층 |
| `service.py` | 비즈니스 로직 |
| `router.py` | API 엔드포인트 |
| `exceptions.py` | 도메인 예외 |

## Import 규칙

### 순서

1. 표준 라이브러리
2. 서드파티 라이브러리
3. 로컬 모듈

```python
# 1. 표준 라이브러리
from datetime import datetime
from typing import Optional

# 2. 서드파티
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

# 3. 로컬 모듈
from app.core.database import get_db
from app.domains.users.service import UserService
```

### isort 설정

```toml
# pyproject.toml
[tool.isort]
profile = "black"
line_length = 100
skip = ["migrations"]
```

## 타입 힌트

### 필수 사용 위치

- 함수 파라미터
- 함수 반환값
- 클래스 속성

```python
from typing import Optional

class UserService:
    repository: UserRepository  # 클래스 속성

    async def get_user(self, user_id: int) -> User:  # 파라미터 + 반환값
        ...

    async def get_users(
        self,
        page: int = 1,
        size: int = 20,
        is_active: Optional[bool] = None,  # Optional 명시
    ) -> tuple[list[User], int]:
        ...
```

### 제네릭 타입

```python
from typing import TypeVar, Generic

DataT = TypeVar("DataT")

class APIResponse(BaseModel, Generic[DataT]):
    success: bool = True
    data: Optional[DataT] = None
```

## 주석 규칙

### 인라인 주석

```python
# ✅ 좋은 예 - 왜(why)를 설명
user.is_active = False  # 탈퇴 처리 시 계정 비활성화

# ❌ 나쁜 예 - 무엇(what)을 설명 (코드로 알 수 있음)
user.is_active = False  # is_active를 False로 설정
```

### TODO 주석

```python
# TODO: Redis 클라이언트 구현 시 활성화
redis_url: str = "redis://localhost:6379/0"
```

### 섹션 구분 (사용 금지)

```python
# ❌ 사용 금지
# =============================================================================
# 성공 응답
# =============================================================================

# ✅ 클래스/함수로 구분
class APIResponse:
    ...

class ErrorResponse:
    ...
```
