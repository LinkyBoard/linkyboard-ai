.PHONY: help install run test lint format migrate migrate-create docker-build docker-up docker-down docker-logs clean

# 색상 정의
YELLOW := \033[1;33m
GREEN := \033[1;32m
NC := \033[0m # No Color

# 기본 변수
PYTHON := poetry run python
UVICORN := poetry run uvicorn
ALEMBIC := poetry run alembic
PYTEST := poetry run pytest
BLACK := poetry run black
ISORT := poetry run isort
FLAKE8 := poetry run flake8
MYPY := poetry run mypy

# 기본 명령어
.DEFAULT_GOAL := help

##@ 도움말
help: ## 사용 가능한 명령어 목록 표시
	@echo "$(GREEN)LinkyBoard AI - 사용 가능한 명령어$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "사용법: make $(YELLOW)<target>$(NC)\n\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(GREEN)%s$(NC)\n", substr($$0, 5) }' $(MAKEFILE_LIST)

##@ 개발 환경
install: ## Poetry 의존성 설치
	poetry install

setup: install ## 의존성 설치 + pre-commit 훅 설정
	poetry run pre-commit install
	poetry run pre-commit install --hook-type commit-msg
	poetry run pre-commit install --hook-type pre-push
	@echo "$(GREEN)✓ 개발 환경 설정 완료$(NC)"

update: ## Poetry 의존성 업데이트
	poetry update

run: ## 개발 서버 실행 (핫 리로드)
	$(UVICORN) app.main:app --host 0.0.0.0 --port 8000 --reload

run-prod: ## 프로덕션 서버 실행
	$(UVICORN) app.main:app --host 0.0.0.0 --port 8000 --workers 4

##@ 테스트
test: ## 전체 테스트 실행
	$(PYTEST) -v

test-unit: ## 단위 테스트만 실행
	$(PYTEST) tests/unit -v

test-integration: ## 통합 테스트만 실행
	$(PYTEST) tests/integration -v

test-e2e: ## E2E 테스트만 실행
	$(PYTEST) tests/e2e -v

test-cov: ## 커버리지 포함 테스트 실행
	$(PYTEST) --cov=app --cov-report=html --cov-report=term-missing

test-cov-unit: ## 단위 테스트 커버리지
	$(PYTEST) tests/unit --cov=app --cov-report=term-missing

test-failed: ## 실패한 테스트만 재실행
	$(PYTEST) --lf -v

test-watch: ## 파일 변경 시 자동 테스트 실행 (pytest-watch 필요)
	poetry run ptw -- -v

##@ 코드 품질
quality: ## 코드 품질 검사 (format + lint)
	@echo "$(GREEN)Running code quality checks...$(NC)"
	$(ISORT) app tests scripts
	$(BLACK) app tests scripts
	$(FLAKE8) app tests scripts
	$(MYPY) app
	@echo "$(GREEN)✓ Code quality checks passed$(NC)"

lint: ## 린트 검사 (flake8 + mypy)
	$(FLAKE8) app tests
	$(MYPY) app

format: ## 코드 포맷팅 (black + isort)
	$(ISORT) app tests
	$(BLACK) app tests

format-check: ## 포맷팅 검사 (수정 없이 확인만)
	$(ISORT) --check-only app tests
	$(BLACK) --check app tests

##@ 데이터베이스
migrate: ## 마이그레이션 적용 (최신 버전으로 업그레이드)
	$(ALEMBIC) upgrade head

migrate-down: ## 마이그레이션 롤백 (한 단계 되돌리기)
	$(ALEMBIC) downgrade -1

migrate-create: ## 새 마이그레이션 생성 (예: make migrate-create name="add_users_table")
	@if [ -z "$(name)" ]; then \
		echo "$(YELLOW)사용법: make migrate-create name=\"마이그레이션_이름\"$(NC)"; \
		exit 1; \
	fi
	$(ALEMBIC) revision --autogenerate -m "$(name)"

migrate-history: ## 마이그레이션 히스토리 조회
	$(ALEMBIC) history

migrate-current: ## 현재 마이그레이션 버전 확인
	$(ALEMBIC) current

##@ Docker
docker-build: ## Docker 이미지 빌드
	docker-compose build

docker-up: ## Docker Compose 환경 실행 (빌드 포함)
	docker-compose up -d --build

docker-down: ## Docker Compose 환경 종료
	docker-compose down

docker-down-v: ## Docker Compose 환경 종료 (볼륨 포함 삭제)
	docker-compose down -v

docker-logs: ## Docker 로그 확인
	docker-compose logs -f

docker-logs-api: ## API 서비스 로그만 확인
	docker-compose logs -f api

docker-exec: ## API 컨테이너 쉘 접속
	docker-compose exec api /bin/bash

docker-ps: ## 실행 중인 컨테이너 확인
	docker-compose ps

##@ LLM & Observability
test-langfuse: ## LangFuse 연결 테스트
	PYTHONPATH=. $(PYTHON) scripts/test_langfuse_connection.py

test-llm: ## LLM 통합 테스트 (실제 API 호출)
	PYTHONPATH=. $(PYTHON) scripts/test_llm_integration.py

##@ 유틸리티
clean: ## 캐시 및 임시 파일 삭제
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	rm -rf htmlcov .coverage 2>/dev/null || true

shell: ## Poetry 가상환경 쉘 실행
	poetry shell

env-example: ## .env.example에서 .env 파일 생성
	cp .env.example .env
	@echo "$(GREEN).env 파일이 생성되었습니다. 필요한 값을 설정해주세요.$(NC)"
