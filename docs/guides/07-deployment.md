# Docker 및 배포

## Docker 구성

### 개발용 (Dockerfile.dev)

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Poetry 설치
RUN pip install --no-cache-dir poetry==1.8.4

# 의존성 설치 (개발 의존성 포함)
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# 소스 복사
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### 프로덕션용 (Dockerfile)

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Poetry 설치
RUN pip install --no-cache-dir poetry==1.8.4

# 의존성 설치 (프로덕션만)
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main

# 소스 복사
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Docker Compose

### 개발 환경 (docker-compose.yml)

```yaml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - .:/app
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/app
      - REDIS_URL=redis://redis:6379/0
      - AUTO_MIGRATE=true
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: app
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

## 환경 변수

### 필수 환경 변수

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `DATABASE_URL` | DB 연결 URL | `postgresql+asyncpg://user:pass@host:5432/db` |
| `SECRET_KEY` | JWT 시크릿 키 | 랜덤 문자열 |

### 선택 환경 변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `DEBUG` | 디버그 모드 | `false` |
| `AUTO_MIGRATE` | 자동 마이그레이션 | `true` |
| `REDIS_URL` | Redis 연결 URL | - |
| `CORS_ORIGINS` | CORS 허용 출처 | `["*"]` |

### .env 파일 예시

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/app

# Security
SECRET_KEY=your-super-secret-key-here

# Application
DEBUG=true
AUTO_MIGRATE=true

# Redis (선택)
REDIS_URL=redis://localhost:6379/0
```

## 실행 명령어

### 개발 환경

```bash
# 전체 서비스 시작
make docker-up

# 로그 확인
make docker-logs

# 서비스 중지
make docker-down

# 볼륨 포함 삭제
docker compose down -v
```

### 프로덕션 환경

```bash
# 이미지 빌드
docker build -t app:latest .

# 컨테이너 실행
docker run -d \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql+asyncpg://... \
  -e SECRET_KEY=... \
  app:latest
```

## Health Check

### 엔드포인트

```
GET /api/health
```

### 응답 예시

```json
{
  "status": "healthy"
}
```

### Docker Health Check

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

## 자동 마이그레이션

서버 시작 시 자동으로 마이그레이션 상태를 확인하고 적용합니다.

```
INFO:     Started server process
INFO:     Checking migration status...
INFO:     Current: None -> Target: 3a95850e3370
INFO:     Running migrations...
INFO:     Migrations completed successfully
INFO:     Application startup complete
```

### 비활성화

```env
AUTO_MIGRATE=false
```

## 배포 체크리스트

### 사전 확인

- [ ] 환경 변수 설정 완료
- [ ] SECRET_KEY 변경
- [ ] DEBUG=false 설정
- [ ] DB 연결 확인
- [ ] 마이그레이션 적용

### 배포 후 확인

- [ ] Health Check 응답 확인
- [ ] API 정상 동작 확인
- [ ] 로그 확인
- [ ] 모니터링 설정

## Makefile 명령어

```makefile
# Docker 관련
docker-up:
    docker compose up -d --build

docker-down:
    docker compose down

docker-logs:
    docker compose logs -f

# 마이그레이션
migrate:
    poetry run alembic upgrade head

migrate-create:
    poetry run alembic revision --autogenerate -m "$(msg)"

# 테스트
test:
    poetry run pytest -v --tb=short

# 코드 품질
lint:
    poetry run black . && poetry run isort .
```
