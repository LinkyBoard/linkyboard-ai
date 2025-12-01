# 신규 도메인 추가 가이드

## 개요

새로운 도메인(예: posts, comments)을 추가할 때의 단계별 가이드입니다.

## 1. 디렉토리 생성

```bash
mkdir -p app/domains/{domain_name}
touch app/domains/{domain_name}/__init__.py
```

```
app/domains/{domain_name}/
├── __init__.py
├── models.py      # SQLAlchemy 모델
├── schemas.py     # Pydantic 스키마
├── repository.py  # 데이터 접근 계층
├── service.py     # 비즈니스 로직
├── router.py      # API 라우터
└── exceptions.py  # 도메인 예외 (선택)
```

## 2. 모델 작성

```python
# app/domains/posts/models.py
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Post(Base):
    """게시글 모델"""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 외래키
    author_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # 관계
    author: Mapped["User"] = relationship("User", back_populates="posts")

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
        return f"<Post(id={self.id}, title={self.title})>"
```

## 3. 스키마 작성

```python
# app/domains/posts/schemas.py
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PostBase(BaseModel):
    """게시글 기본 스키마"""

    title: str = Field(..., min_length=1, max_length=200, description="제목")
    content: str = Field(..., min_length=1, description="내용")


class PostCreate(PostBase):
    """게시글 생성 요청"""

    pass


class PostUpdate(BaseModel):
    """게시글 수정 요청"""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)


class PostResponse(PostBase):
    """게시글 응답"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    author_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
```

## 4. Repository 작성

```python
# app/domains/posts/repository.py
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.posts.models import Post


class PostRepository:
    """게시글 리포지토리"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, post_id: int) -> Optional[Post]:
        result = await self.session.execute(
            select(Post).where(Post.id == post_id)
        )
        return result.scalar_one_or_none()

    async def get_list(
        self,
        skip: int = 0,
        limit: int = 20,
        author_id: Optional[int] = None,
    ) -> Sequence[Post]:
        query = select(Post)

        if author_id is not None:
            query = query.where(Post.author_id == author_id)

        query = query.offset(skip).limit(limit).order_by(Post.created_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count(self, author_id: Optional[int] = None) -> int:
        query = select(func.count(Post.id))

        if author_id is not None:
            query = query.where(Post.author_id == author_id)

        result = await self.session.execute(query)
        return result.scalar_one()

    async def create(self, post: Post) -> Post:
        self.session.add(post)
        await self.session.flush()
        await self.session.refresh(post)
        return post

    async def update(self, post: Post) -> Post:
        await self.session.flush()
        await self.session.refresh(post)
        return post

    async def delete(self, post: Post) -> None:
        await self.session.delete(post)
        await self.session.flush()
```

## 5. 예외 정의 (선택)

```python
# app/domains/posts/exceptions.py
from app.core.exceptions import NotFoundException, BusinessException


class PostNotFoundException(NotFoundException):
    """게시글을 찾을 수 없음"""

    def __init__(self, post_id: int):
        super().__init__(detail=f"Post with id {post_id} not found")


class PostPermissionDeniedException(BusinessException):
    """게시글 수정/삭제 권한 없음"""

    def __init__(self):
        super().__init__(detail="You don't have permission to modify this post")
```

## 6. Service 작성

```python
# app/domains/posts/service.py
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.posts.exceptions import PostNotFoundException
from app.domains.posts.models import Post
from app.domains.posts.repository import PostRepository
from app.domains.posts.schemas import PostCreate, PostUpdate


class PostService:
    """게시글 서비스"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = PostRepository(session)

    async def get_post(self, post_id: int) -> Post:
        post = await self.repository.get_by_id(post_id)
        if not post:
            raise PostNotFoundException(post_id)
        return post

    async def get_posts(
        self,
        skip: int = 0,
        limit: int = 20,
        author_id: Optional[int] = None,
    ) -> tuple[Sequence[Post], int]:
        posts = await self.repository.get_list(
            skip=skip,
            limit=limit,
            author_id=author_id
        )
        total = await self.repository.count(author_id=author_id)
        return posts, total

    async def create_post(
        self,
        data: PostCreate,
        author_id: int
    ) -> Post:
        post = Post(
            title=data.title,
            content=data.content,
            author_id=author_id,
        )
        return await self.repository.create(post)

    async def update_post(
        self,
        post_id: int,
        data: PostUpdate
    ) -> Post:
        post = await self.get_post(post_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(post, field, value)

        return await self.repository.update(post)

    async def delete_post(self, post_id: int) -> None:
        post = await self.get_post(post_id)
        await self.repository.delete(post)
```

## 7. Router 작성

```python
# app/domains/posts/router.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.posts.schemas import PostCreate, PostResponse, PostUpdate
from app.domains.posts.service import PostService
from app.schemas.response import APIResponse, ListAPIResponse
from app.utils.response import create_response, create_list_response


router = APIRouter(prefix="/posts", tags=["posts"])


def get_post_service(session: AsyncSession = Depends(get_db)) -> PostService:
    return PostService(session)


@router.get(
    "/",
    response_model=ListAPIResponse[PostResponse],
    summary="게시글 목록 조회",
)
async def get_posts(
    page: int = 1,
    size: int = 20,
    service: PostService = Depends(get_post_service),
):
    skip = (page - 1) * size
    posts, total = await service.get_posts(skip=skip, limit=size)
    return create_list_response(
        items=[PostResponse.model_validate(p) for p in posts],
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/{post_id}",
    response_model=APIResponse[PostResponse],
    summary="게시글 상세 조회",
)
async def get_post(
    post_id: int,
    service: PostService = Depends(get_post_service),
):
    post = await service.get_post(post_id)
    return create_response(data=PostResponse.model_validate(post))


@router.post(
    "/",
    response_model=APIResponse[PostResponse],
    status_code=status.HTTP_201_CREATED,
    summary="게시글 생성",
)
async def create_post(
    data: PostCreate,
    service: PostService = Depends(get_post_service),
):
    # TODO: author_id는 인증된 사용자에서 가져오기
    post = await service.create_post(data, author_id=1)
    return create_response(
        data=PostResponse.model_validate(post),
        code="CREATED",
        message="게시글이 생성되었습니다.",
    )


@router.patch(
    "/{post_id}",
    response_model=APIResponse[PostResponse],
    summary="게시글 수정",
)
async def update_post(
    post_id: int,
    data: PostUpdate,
    service: PostService = Depends(get_post_service),
):
    post = await service.update_post(post_id, data)
    return create_response(
        data=PostResponse.model_validate(post),
        code="UPDATED",
        message="게시글이 수정되었습니다.",
    )


@router.delete(
    "/{post_id}",
    response_model=APIResponse[None],
    summary="게시글 삭제",
)
async def delete_post(
    post_id: int,
    service: PostService = Depends(get_post_service),
):
    await service.delete_post(post_id)
    return create_response(
        code="DELETED",
        message="게시글이 삭제되었습니다.",
    )
```

## 8. 라우터 등록

```python
# app/api/v1/__init__.py
from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.domains.users.router import router as users_router
from app.domains.posts.router import router as posts_router  # 추가

router = APIRouter(prefix="/api/v1")

router.include_router(health_router)
router.include_router(users_router)
router.include_router(posts_router)  # 추가
```

## 9. 마이그레이션 생성

```bash
make migrate-create msg="create_posts_table"
make migrate
```

## 10. 테스트 작성

```bash
mkdir -p tests/unit/domains/posts
mkdir -p tests/integration/api/v1
```

```python
# tests/unit/domains/posts/test_service.py
# tests/integration/api/v1/test_posts.py
```

## 체크리스트

### 필수

- [ ] 모델 작성 및 관계 설정
- [ ] 스키마 작성 (Create, Update, Response)
- [ ] Repository 작성
- [ ] Service 작성
- [ ] Router 작성
- [ ] 라우터 등록
- [ ] 마이그레이션 생성 및 적용

### 권장

- [ ] 도메인 예외 정의
- [ ] 단위 테스트 작성
- [ ] 통합 테스트 작성
- [ ] API 문서 확인 (/docs)
