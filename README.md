# FastAPI Project Template

FastAPI 기반의 도메인 주도 설계(DDD) 백엔드 템플릿입니다.

## 🚀 템플릿 사용법

### 1. 템플릿 복사

```bash
# 새 프로젝트 디렉토리로 복사
cp -r fastapi-ddd-template my-new-project
cd my-new-project

# Git 초기화
rm -rf .git
git init
```

### 2. 프로젝트명 변경

다음 파일들에서 프로젝트명을 변경하세요:

| 파일 | 변경 항목 |
|------|----------|
| `pyproject.toml` | `name`, `description`, `authors` |
| `.env.example` | `APP_NAME`, `DATABASE_URL` (DB명) |
| `docker-compose.yml` | `container_name`, `POSTGRES_DB` |
| `app/core/config.py` | `app_name`, `database_url` 기본값 |

### 3. 의존성 설치 및 실행

```bash
make install
cp .env.example .env
make docker-up
```

## 기술 스택

- **Framework**: FastAPI
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy 2.0
- **Migration**: Alembic
- **Package Manager**: Poetry
- **Container**: Docker & Docker Compose

## 프로젝트 구조

```
.
├── app/
│   ├── api/
│   │   └── v1/           # API v1 라우터
│   ├── core/
│   │   ├── config.py     # 환경 설정
│   │   ├── database.py   # DB 연결
│   │   ├── exceptions.py # 전역 예외 처리
│   │   ├── logging.py    # 로깅 설정
│   │   ├── middlewares/  # 미들웨어
│   │   │   ├── context.py    # 요청 ID 컨텍스트
│   │   │   └── logging.py    # 로깅 미들웨어
│   │   └── utils/        # 유틸리티
│   │       ├── datetime.py   # 날짜/시간
│   │       └── pagination.py # 페이지네이션
│   ├── domains/          # 도메인 모듈
│   │   └── users/        # 사용자 도메인 예시
│   │       ├── router.py
│   │       ├── service.py
│   │       ├── repository.py
│   │       ├── models.py
│   │       ├── schemas.py
│   │       └── exceptions.py
│   └── main.py           # 애플리케이션 엔트리포인트
├── migrations/           # Alembic 마이그레이션
├── tests/                # 테스트
├── docs/
│   ├── guides/           # 개발 가이드 (프로젝트 구조, 코드 규칙)
│   └── requirements/     # 서비스 요구사항 및 기획 문서
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── pyproject.toml
└── README.md
```

## 시작하기

### 필수 요구사항

- Python 3.13+
- Poetry
- Docker & Docker Compose

### 로컬 개발 환경 설정

```bash
# Poetry 의존성 설치
make install

# 환경 변수 설정
cp .env.example .env

# pre-commit 훅 설치
poetry run pre-commit install
poetry run pre-commit install --hook-type pre-push

# 데이터베이스 마이그레이션
make migrate

# 개발 서버 실행
make run
```

### Docker로 실행

```bash
# 전체 환경 실행 (빌드 포함)
make docker-up

# 환경 종료
make docker-down

# 로그 확인
make docker-logs
```

## 명령어 목록

```bash
make help           # 사용 가능한 명령어 목록
make install        # Poetry 의존성 설치
make run            # 개발 서버 실행
make test           # 테스트 실행
make lint           # 린트 검사
make format         # 코드 포맷팅
make migrate        # DB 마이그레이션 적용
make migrate-create # 새 마이그레이션 생성
make docker-build   # Docker 이미지 빌드
make docker-up      # Docker Compose 환경 실행
make docker-down    # Docker Compose 환경 종료
```

## API 문서

서버 실행 후 다음 URL에서 API 문서를 확인할 수 있습니다:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- API v1 Base URL: http://localhost:8000/api/v1

## 🛠 주요 기능

### 미들웨어
- **요청 ID 추적**: 모든 요청에 `X-Request-ID` 헤더 자동 부여
- **요청/응답 로깅**: 메서드, 경로, 상태코드, 처리시간 자동 로깅
- **처리 시간 측정**: `X-Process-Time` 헤더로 응답 시간 확인

### 유틸리티
- **날짜/시간**: UTC/KST 변환, 포맷팅, 파싱 함수
- **페이지네이션**: `PageParams` 의존성, `PageResponse` 스키마

### API 버저닝
- `/api/v1/` 경로로 버전 관리
- 새 버전 추가 시 `app/api/v2/` 생성

## 📁 새 도메인 추가하기

`app/domains/users/` 구조를 참고하여 새 도메인을 추가하세요:

```bash
app/domains/
├── users/          # 예시 도메인
│   ├── __init__.py
│   ├── router.py      # API 라우터
│   ├── service.py     # 비즈니스 로직
│   ├── repository.py  # 데이터 접근
│   ├── models.py      # SQLAlchemy 모델
│   ├── schemas.py     # Pydantic 스키마
│   └── exceptions.py  # 도메인 예외
└── your_domain/    # 새 도메인
    └── ...
```

새 도메인 라우터는 `app/api/__init__.py`에 등록하세요.

## 📝 License

MIT
