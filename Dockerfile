# 빌드 스테이지
FROM python:3.13-slim as builder

# 환경 변수 설정
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Poetry 설치
RUN pip install poetry==1.8.4

WORKDIR /app

# 의존성 파일 복사
COPY pyproject.toml poetry.lock* ./

# 가상 환경 생성하지 않고 시스템에 직접 설치
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main

# 프로덕션 스테이지
FROM python:3.13-slim as production

# 버전 정보 (빌드 시 주입)
ARG APP_VERSION=v0.1.0
ENV APP_VERSION=$APP_VERSION

# 환경 변수 설정
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# 필요한 시스템 패키지 설치
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 빌더에서 설치된 패키지 복사
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 애플리케이션 코드 복사
COPY . .

# 비root 사용자 생성 및 전환
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app

USER appuser

# 헬스 체크
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 포트 노출
EXPOSE 8000

# 애플리케이션 실행
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
