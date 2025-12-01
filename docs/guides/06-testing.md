# 테스트 규칙

## 테스트 구조

```
tests/
├── conftest.py              # 전역 픽스처
├── unit/                    # 단위 테스트
│   └── domains/
│       └── users/
│           ├── test_schemas.py
│           ├── test_service.py
│           └── test_repository.py
├── integration/             # 통합 테스트
│   └── api/
│       └── v1/
│           └── test_users.py
└── e2e/                     # E2E 테스트
    └── test_user_flow.py
```

## 테스트 레벨 정의

### Unit Test (단위 테스트)

- 외부 의존성 없이 순수 로직만 테스트
- Mock을 사용하여 의존성 격리
- DB, 외부 API 호출 없음

```python
# tests/unit/domains/users/test_service.py
from unittest.mock import AsyncMock

import pytest

from app.domains.users.service import UserService


class TestUserService:
    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session):
        return UserService(mock_session)

    @pytest.mark.asyncio
    async def test_create_user_success(self, service, mock_session):
        """사용자 생성 성공"""
        ...

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(self, service, mock_session):
        """중복 사용자명 예외"""
        ...
```

### Integration Test (통합 테스트)

- API 엔드포인트 테스트
- 인메모리 DB 사용 (SQLite)
- 실제 데이터 흐름 검증

```python
# tests/integration/api/v1/test_users.py
import pytest
from httpx import AsyncClient

from app.schemas.response import SuccessCode


class TestUserAPI:
    @pytest.mark.asyncio
    async def test_create_user(self, client: AsyncClient):
        """사용자 생성 API"""
        response = await client.post(
            "/api/v1/users/",
            json={
                "username": "testuser",
                "password": "password123",
                "full_name": "Test User",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["code"] == SuccessCode.CREATED
        assert data["data"]["username"] == "testuser"
```

### E2E Test (End-to-End 테스트)

- 전체 사용자 시나리오 테스트
- 실제 DB 연결 필요
- CI/CD에서는 스킵 가능

```python
# tests/e2e/test_user_flow.py
import pytest

from tests.conftest import is_db_available


@pytest.mark.skipif(
    not is_db_available(),
    reason="Database not available"
)
class TestUserFlow:
    @pytest.mark.asyncio
    async def test_full_user_lifecycle(self, real_client):
        """사용자 전체 라이프사이클"""
        # 1. 생성
        # 2. 조회
        # 3. 수정
        # 4. 삭제
        ...
```

## Fixture 설정

### conftest.py 구조

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app

# 테스트용 인메모리 DB
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def is_db_available() -> bool:
    """실제 DB 연결 가능 여부"""
    # 구현...


@pytest_asyncio.fixture
async def session():
    """테스트용 DB 세션"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def client(session: AsyncSession):
    """테스트용 HTTP 클라이언트"""
    app.dependency_overrides[get_db] = lambda: session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()
```

## 네이밍 규칙

### 테스트 파일

```
test_{테스트_대상}.py

예시:
- test_schemas.py
- test_service.py
- test_users.py
```

### 테스트 함수

```python
def test_{동작}_{조건}_{결과}():
    ...

# 예시
def test_create_user_success():
def test_create_user_duplicate_username_raises_error():
def test_get_user_not_found_returns_none():
```

### 테스트 클래스

```python
class Test{테스트대상}:
    ...

# 예시
class TestUserService:
class TestUserAPI:
class TestUserFlow:
```

## 테스트 실행

### 명령어

```bash
# 전체 테스트
make test

# 단위 테스트만
pytest tests/unit -v

# 통합 테스트만
pytest tests/integration -v

# 특정 파일
pytest tests/unit/domains/users/test_service.py -v

# 특정 테스트
pytest tests/unit/domains/users/test_service.py::TestUserService::test_create_user -v

# 커버리지
pytest --cov=app --cov-report=html
```

### pytest.ini 설정

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
filterwarnings =
    ignore::DeprecationWarning
```

## Pre-push 테스트

커밋 푸시 전 자동으로 전체 테스트가 실행됩니다.

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: pytest
      name: pytest
      entry: poetry run pytest -v --tb=short
      language: system
      pass_filenames: false
      always_run: true
      stages: [pre-push]
```

## 테스트 작성 원칙

1. **AAA 패턴** (Arrange-Act-Assert)
   ```python
   def test_example():
       # Arrange (준비)
       user = User(username="test")

       # Act (실행)
       result = service.create(user)

       # Assert (검증)
       assert result.id is not None
   ```

2. **하나의 테스트, 하나의 검증**
   - 한 테스트에서 여러 시나리오 테스트 지양
   - 명확한 실패 원인 파악 가능

3. **독립적인 테스트**
   - 테스트 간 의존성 없음
   - 실행 순서에 영향받지 않음

4. **읽기 쉬운 테스트**
   - 테스트 이름으로 의도 파악 가능
   - 불필요한 추상화 지양
