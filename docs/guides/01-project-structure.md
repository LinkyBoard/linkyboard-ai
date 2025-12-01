# 프로젝트 구조

## 개요

이 프로젝트는 **FastAPI** 기반의 **도메인 주도 설계(DDD)** 백엔드 템플릿입니다.

## 기술 스택

| 카테고리 | 기술 |
|----------|------|
| Framework | FastAPI |
| Language | Python 3.13+ |
| Database | PostgreSQL |
| ORM | SQLAlchemy 2.0 (async) |
| Migration | Alembic |
| Package Manager | Poetry |
| Container | Docker & Docker Compose |
| Testing | pytest, pytest-asyncio |

## 디렉토리 구조

```
.
├── app/                          # 애플리케이션 코드
│   ├── api/                      # API 라우터
│   │   └── v1/                   # API 버전 1
│   │       └── __init__.py       # 라우터 통합
│   ├── core/                     # 핵심 모듈
│   │   ├── config.py             # 환경 설정
│   │   ├── database.py           # DB 연결
│   │   ├── exceptions.py         # 전역 예외
│   │   ├── logging.py            # 로깅 설정
│   │   ├── migration.py          # 마이그레이션 유틸리티
│   │   ├── schemas.py            # 공통 스키마
│   │   ├── middlewares/          # 미들웨어
│   │   │   ├── context.py        # 요청 ID 컨텍스트
│   │   │   └── logging.py        # 로깅 미들웨어
│   │   └── utils/                # 유틸리티
│   │       ├── datetime.py       # 날짜/시간
│   │       └── pagination.py     # 페이지네이션
│   ├── domains/                  # 도메인 모듈
│   │   └── users/                # 사용자 도메인 (예제)
│   │       ├── __init__.py
│   │       ├── models.py         # SQLAlchemy 모델
│   │       ├── schemas.py        # Pydantic 스키마
│   │       ├── repository.py     # 데이터 접근 계층
│   │       ├── service.py        # 비즈니스 로직
│   │       ├── router.py         # API 엔드포인트
│   │       └── exceptions.py     # 도메인 예외
│   └── main.py                   # 앱 엔트리포인트
├── migrations/                   # Alembic 마이그레이션
│   ├── env.py
│   └── versions/
├── tests/                        # 테스트
│   ├── unit/                     # 단위 테스트
│   ├── integration/              # 통합 테스트
│   └── e2e/                      # E2E 테스트
├── docs/                         # 문서
│   └── requirements/             # 요구사항 문서
├── docker-compose.yml            # Docker Compose 설정
├── Dockerfile                    # 프로덕션 Dockerfile
├── Dockerfile.dev                # 개발 Dockerfile
├── Makefile                      # 명령어 단축
├── pyproject.toml                # Poetry 설정
├── alembic.ini                   # Alembic 설정
└── .pre-commit-config.yaml       # pre-commit 설정
```

## 계층 구조

```
┌─────────────────────────────────────────────────┐
│                    Router                        │  ← HTTP 요청/응답 처리
│              (app/domains/*/router.py)           │
├─────────────────────────────────────────────────┤
│                    Service                       │  ← 비즈니스 로직
│             (app/domains/*/service.py)           │
├─────────────────────────────────────────────────┤
│                   Repository                     │  ← 데이터 접근
│            (app/domains/*/repository.py)         │
├─────────────────────────────────────────────────┤
│                     Model                        │  ← DB 엔티티
│             (app/domains/*/models.py)            │
└─────────────────────────────────────────────────┘
```

## API 버저닝

- 모든 API는 `/api/v1/` prefix를 사용
- 새 버전 추가 시 `app/api/v2/` 디렉토리 생성
- `app/main.py`에서 라우터 등록

```python
# app/main.py
app.include_router(api_v1_router, prefix="/api/v1")
# app.include_router(api_v2_router, prefix="/api/v2")  # 추후 추가
```

## 새 도메인 추가 방법

1. `app/domains/<domain_name>/` 디렉토리 생성
2. 아래 파일 생성:
   - `__init__.py`
   - `models.py`
   - `schemas.py`
   - `repository.py`
   - `service.py`
   - `router.py`
   - `exceptions.py`
3. `app/api/v1/__init__.py`에 라우터 등록

```python
# app/api/v1/__init__.py
from app.domains.posts.router import router as posts_router

api_router.include_router(posts_router, prefix="/posts", tags=["Posts"])
```
