# pipenv 
.PHONY: freeze
freeze:
	pipenv requirements > requirements.txt

# fastapi
.PHONY: run
run:
	uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload

# docker
.PHONY: build
build:
	docker build -t linkyboard-ai .

.PHONY: run-docker
run-docker:
	docker run -d -p 8001:80 --name linkyboard-ai linkyboard-ai

.PHONY: stop-docker
stop-docker:
	docker stop linkyboard-ai

.PHONY: remove-docker
remove-docker:
	docker rm linkyboard-ai

# docker-compose
.PHONY: build-compose
build-compose:
	docker-compose build

.PHONY: up-compose
up-compose:
	docker-compose up -d

.PHONY: down-compose
down-compose:
	docker-compose down	

# docker cleanup (for EC2 disk space issues)
.PHONY: docker-cleanup
docker-cleanup:
	@echo "🧹 Docker 시스템 정리"
	@echo "📊 정리 전 디스크 사용량:"
	docker system df
	@echo ""
	@echo "🗑️  사용하지 않는 컨테이너, 네트워크, 이미지 정리..."
	docker system prune -f
	@echo ""
	@echo "🗑️  사용하지 않는 볼륨 정리..."
	docker volume prune -f
	@echo ""
	@echo "🗑️  댕글링 이미지 정리..."
	docker image prune -f
	@echo ""
	@echo "📊 정리 후 디스크 사용량:"
	docker system df
	@echo "✅ Docker 정리 완료!"

.PHONY: docker-cleanup-all
docker-cleanup-all:
	@echo "🧹 Docker 전체 정리 (위험: 모든 미사용 리소스 삭제)"
	@echo "📊 정리 전 디스크 사용량:"
	docker system df
	@echo ""
	@echo "⚠️  모든 미사용 리소스 정리 중..."
	docker system prune -a -f --volumes
	@echo ""
	@echo "📊 정리 후 디스크 사용량:"
	docker system df
	@echo "✅ Docker 전체 정리 완료!"

# alembic
.PHONY: upgrade
upgrade:
	alembic upgrade head

.PHONY: downgrade
downgrade:
	alembic downgrade -1

# alembic for production
.PHONY: upgrade-prod
upgrade-prod:
	@echo "🗃 Production Alembic Migration"
	@if [ ! -f .env ]; then echo "❌ .env file not found"; exit 1; fi
	@eval $$(grep -E '^(POSTGRES_HOST|POSTGRES_PORT|POSTGRES_USER|POSTGRES_PASSWORD)=' .env | sed 's/^/export /') && \
	export DATABASE_URL="postgresql://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@$${POSTGRES_HOST}:$${POSTGRES_PORT}/prod" && \
	echo "✅ Connecting to: $${POSTGRES_HOST}:$${POSTGRES_PORT}/prod" && \
	alembic upgrade head

.PHONY: downgrade-prod
downgrade-prod:
	@echo "🔄 Production Alembic Downgrade"
	@if [ ! -f .env ]; then echo "❌ .env file not found"; exit 1; fi
	@eval $$(grep -E '^(POSTGRES_HOST|POSTGRES_PORT|POSTGRES_USER|POSTGRES_PASSWORD)=' .env | sed 's/^/export /') && \
	export DATABASE_URL="postgresql://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@$${POSTGRES_HOST}:$${POSTGRES_PORT}/prod" && \
	echo "✅ Connecting to: $${POSTGRES_HOST}:$${POSTGRES_PORT}/prod" && \
	alembic downgrade -1

.PHONY: current-prod
current-prod:
	@echo "📋 Production Alembic Current Status"
	@if [ ! -f .env ]; then echo "❌ .env file not found"; exit 1; fi
	@eval $$(grep -E '^(POSTGRES_HOST|POSTGRES_PORT|POSTGRES_USER|POSTGRES_PASSWORD)=' .env | sed 's/^/export /') && \
	export DATABASE_URL="postgresql://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@$${POSTGRES_HOST}:$${POSTGRES_PORT}/prod" && \
	echo "✅ Connecting to: $${POSTGRES_HOST}:$${POSTGRES_PORT}/prod" && \
	alembic current -v

.PHONY: history-prod
history-prod:
	@echo "📜 Production Alembic Migration History"
	@if [ ! -f .env ]; then echo "❌ .env file not found"; exit 1; fi
	@eval $$(grep -E '^(POSTGRES_HOST|POSTGRES_PORT|POSTGRES_USER|POSTGRES_PASSWORD)=' .env | sed 's/^/export /') && \
	export DATABASE_URL="postgresql://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@$${POSTGRES_HOST}:$${POSTGRES_PORT}/prod" && \
	echo "✅ Connecting to: $${POSTGRES_HOST}:$${POSTGRES_PORT}/prod" && \
	alembic history -v

# pytest
.PHONY: test test-unit test-functional test-verbose test-file test-cov

test:
	@echo "🧪 Running all tests (unit and functional)..."
	pipenv run pytest tests/unit tests/functional

test-unit:
	@echo "🧪 Running unit tests..."
	pipenv run pytest tests/unit

test-functional:
	@echo "🧪 Running functional tests..."
	pipenv run pytest tests/functional

test-verbose:
	@echo "🧪 Running all tests with verbose output..."
	pipenv run pytest -v tests/unit tests/functional

test-file:
	@echo "🧪 Running tests for file: $(path)"
	pipenv run pytest $(path)

test-cov:
	@echo "🧪 Running unit tests and generating coverage report..."
	pipenv run pytest --cov=app --cov-report=html tests/unit
	@echo "📊 Opening coverage report..."
	open htmlcov/index.html

# AI 모델 카탈로그 관리
.PHONY: models-check models-init models-sync-to-prod models-from-file models-test

models-check:
	@echo "🤖 Dev 데이터베이스의 AI 모델 정보 확인..."
	pipenv run python scripts/check_models.py

models-test:
	@echo "🧪 AI 모델 카탈로그 관리 시스템 테스트..."
	pipenv run python scripts/test_model_catalog.py

models-init:
	@echo "🤖 새 데이터베이스에 초기 AI 모델 설정..."
	@if [ ! -f .env ]; then echo "❌ .env file not found"; exit 1; fi
	@eval $$(grep -E '^(POSTGRES_HOST|POSTGRES_PORT|POSTGRES_USER|POSTGRES_PASSWORD)=' .env | sed 's/^/export /') && \
	export TARGET_DB="$${POSTGRES_DB:-dev}" && \
	export DATABASE_URL="postgresql://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@$${POSTGRES_HOST}:$${POSTGRES_PORT}/$${TARGET_DB}" && \
	echo "✅ 데이터베이스에 초기 모델 설정: $${POSTGRES_HOST}:$${POSTGRES_PORT}/$${TARGET_DB}" && \
	pipenv run python scripts/manage_model_catalog.py --action init --database-url "$${DATABASE_URL}"

models-sync-to-prod:
	@echo "🤖 Dev에서 Prod로 AI 모델 동기화..."
	@if [ ! -f .env ]; then echo "❌ .env file not found"; exit 1; fi
	@eval $$(grep -E '^(POSTGRES_HOST|POSTGRES_PORT|POSTGRES_USER|POSTGRES_PASSWORD|POSTGRES_DB)=' .env | sed 's/^/export /') && \
	export DEV_DATABASE_URL="postgresql://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@$${POSTGRES_HOST}:$${POSTGRES_PORT}/$${POSTGRES_DB}" && \
	export PROD_DATABASE_URL="postgresql://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@$${POSTGRES_HOST}:$${POSTGRES_PORT}/prod" && \
	echo "✅ Dev에서 Prod로 모델 동기화: $${POSTGRES_HOST}:$${POSTGRES_PORT}" && \
	pipenv run python scripts/manage_model_catalog.py --action sync --database-url "$${PROD_DATABASE_URL}" --dev-database-url "$${DEV_DATABASE_URL}"

models-from-file:
	@echo "🤖 파일에서 AI 모델 데이터 로드..."
	@if [ ! -f .env ]; then echo "❌ .env file not found"; exit 1; fi
	@if [ -z "$(file)" ]; then echo "❌ Usage: make models-from-file file=model_catalog_data.json"; exit 1; fi
	@eval $$(grep -E '^(POSTGRES_HOST|POSTGRES_PORT|POSTGRES_USER|POSTGRES_PASSWORD)=' .env | sed 's/^/export /') && \
	export TARGET_DB="$${POSTGRES_DB:-dev}" && \
	export DATABASE_URL="postgresql://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@$${POSTGRES_HOST}:$${POSTGRES_PORT}/$${TARGET_DB}" && \
	echo "✅ 파일에서 모델 로드: $(file) -> $${POSTGRES_HOST}:$${POSTGRES_PORT}/$${TARGET_DB}" && \
	pipenv run python scripts/manage_model_catalog.py --action from-file --database-url "$${DATABASE_URL}" --file "$(file)"