# 데이터베이스 규칙

## SQLAlchemy 모델 작성

### 기본 구조

```python
# app/domains/users/models.py
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    """사용자 모델"""

    __tablename__ = "users"

    # Primary Key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 필수 필드
    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # 선택 필드
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # 상태 필드
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"
```

### 타입 매핑

| Python 타입 | SQLAlchemy 타입 |
|-------------|-----------------|
| `str` | `String(length)` |
| `int` | `Integer` |
| `bool` | `Boolean` |
| `datetime` | `DateTime(timezone=True)` |
| `Optional[T]` | `nullable=True` |

## Repository 패턴

### 기본 구조

```python
# app/domains/users/repository.py
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.users.models import User


class UserRepository:
    """사용자 리포지토리"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """ID로 조회"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_list(
        self,
        skip: int = 0,
        limit: int = 20,
        is_active: Optional[bool] = None,
    ) -> Sequence[User]:
        """목록 조회"""
        query = select(User)

        if is_active is not None:
            query = query.where(User.is_active == is_active)

        query = query.offset(skip).limit(limit).order_by(User.created_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count(self, is_active: Optional[bool] = None) -> int:
        """개수 조회"""
        query = select(func.count(User.id))

        if is_active is not None:
            query = query.where(User.is_active == is_active)

        result = await self.session.execute(query)
        return result.scalar_one()

    async def create(self, user: User) -> User:
        """생성"""
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update(self, user: User) -> User:
        """수정"""
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        """삭제"""
        await self.session.delete(user)
        await self.session.flush()

    async def exists_by_username(
        self,
        username: str,
        exclude_id: Optional[int] = None
    ) -> bool:
        """사용자명 존재 여부"""
        query = select(User.id).where(User.username == username)
        if exclude_id:
            query = query.where(User.id != exclude_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None
```

## 마이그레이션

### 자동 마이그레이션

서버 시작 시 자동으로 마이그레이션이 실행됩니다.

```python
# app/core/config.py
auto_migrate: bool = True  # 환경변수: AUTO_MIGRATE
```

### 수동 마이그레이션

```bash
# 새 마이그레이션 생성
make migrate-create msg="add_posts_table"

# 마이그레이션 적용
make migrate

# 롤백
poetry run alembic downgrade -1
```

### 마이그레이션 파일 예시

```python
# migrations/versions/xxx_create_users_table.py
def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_username', 'users', ['username'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_username', table_name='users')
    op.drop_table('users')
```

## 세션 관리

### 의존성 주입

```python
# app/core/database.py
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

### Service에서 사용

```python
# app/domains/users/router.py
def get_user_service(session: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(session)

@router.get("/{user_id}")
async def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
):
    ...
```

## 인덱스 규칙

| 상황 | 인덱스 타입 |
|------|------------|
| 자주 조회하는 필드 | `index=True` |
| 유니크 제약 | `unique=True` |
| 복합 조건 검색 | 복합 인덱스 |
| 외래키 | 자동 생성 (권장) |
