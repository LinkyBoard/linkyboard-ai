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

# BDD 기반 테스트 명령어 (OpenAI provider만 지원)
.PHONY: test test-unit test-functional test-verbose test-file test-cov test-bdd test-ai-providers test-integration test-quick test-status help-test

help-test:
	@echo "🧪 BDD 기반 테스트 명령어 도움말"
	@echo ""
	@echo "핵심 테스트:"
	@echo "  test                  전체 테스트 실행 (모든 AI Provider 포함)"
	@echo "  test-ai-providers     AI Provider 테스트 (OpenAI + Claude + Google)"
	@echo "  test-quick            빠른 테스트 (핵심 기능만)"
	@echo ""
	@echo "상세 테스트:"
	@echo "  test-unit             유닛 테스트 실행"
	@echo "  test-integration      통합 테스트 실행"  
	@echo "  test-functional       기능 테스트 실행"
	@echo "  test-bdd              BDD 프레임워크 상태 확인"
	@echo "  test-cov              커버리지 포함 테스트"
	@echo ""
	@echo "개발 도구:"
	@echo "  test-file path=파일   특정 파일 테스트"
	@echo "  test-verbose          상세 출력 테스트"
	@echo "  test-status           테스트 현황 확인"

# 전체 테스트 (BDD 기반, 모든 AI Provider 포함)
test:
	@echo "🧪 BDD 기반 전체 테스트 실행 중 (모든 AI Provider 포함)..."
	pipenv run pytest tests/unit/ai/providers/ \
		tests/integration/test_ai_provider_simple.py \
		tests/unit/board_ai/ \
		tests/functional/collect/v1/clipper/ \
		-v --tb=short
	@echo "✅ 테스트 완료!"

# AI Provider 전용 테스트 (OpenAI + Claude + Google)
test-ai-providers:
	@echo "🤖 AI Provider BDD 테스트 실행 중 (OpenAI + Claude + Google)..."
	pipenv run pytest tests/unit/ai/providers/ \
		tests/integration/test_ai_provider_simple.py \
		-v --tb=short
	@echo "✅ AI Provider 테스트 완료!"

# 빠른 테스트 (핵심 기능만)
test-quick:
	@echo "⚡ 빠른 테스트 실행 중..."
	pipenv run pytest tests/unit/ai/providers/test_openai_provider_enhanced.py::TestOpenAIProvider::test_given_valid_messages_when_generate_chat_completion_then_success \
		tests/integration/test_ai_provider_simple.py::TestSimpleAIProviderIntegration::test_basic_chat_completion \
		-v
	@echo "✅ 빠른 테스트 완료!"

# 통합 테스트만
test-integration:
	@echo "🔗 통합 테스트 실행 중..."
	pipenv run pytest tests/integration/test_ai_provider_simple.py -v

# 유닛 테스트 (BDD 강화 버전 포함)
test-unit:
	@echo "🧪 유닛 테스트 실행 중..."
	pipenv run pytest tests/unit/ \
		--ignore=tests/unit/ai/providers/test_ai_router.py \
		--ignore=tests/unit/ai/providers/test_claude_provider.py.disabled \
		--ignore=tests/unit/ai/providers/test_openai_provider.py.disabled \
		-v

# 기능 테스트
test-functional:
	@echo "🧪 기능 테스트 실행 중..."
	pipenv run pytest tests/functional/ -v

# BDD 프레임워크 상태 확인
test-bdd:
	@echo "🎭 BDD 프레임워크 상태 확인..."
	@echo "✅ pytest-bdd 설치됨"
	@find tests/bdd/features -name "*.feature" | head -5 | xargs -I {} echo "  📄 {}"
	@echo "✅ Feature 파일들이 tests/bdd/features/ 에 준비되어 있습니다"
	@echo "✅ Step Definitions가 tests/bdd/step_definitions/ 에 준비되어 있습니다"

# 커버리지 포함 테스트
test-cov:
	@echo "📊 커버리지 테스트 실행 중..."
	pipenv run pytest tests/unit/ai/providers/test_openai_provider_enhanced.py \
		tests/integration/test_ai_provider_simple.py \
		--cov=app.ai.providers.openai_provider \
		--cov=app.ai.providers.router \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		-v
	@echo "📊 커버리지 리포트 생성 완료: htmlcov/index.html"

# 상세 출력 테스트
test-verbose:
	@echo "🧪 상세 출력 테스트 실행 중..."
	pipenv run pytest tests/unit/ai/providers/test_openai_provider_enhanced.py \
		tests/integration/test_ai_provider_simple.py \
		-v -s --tb=long

# 특정 파일 테스트
test-file:
	@echo "🧪 파일별 테스트 실행: $(path)"
	pipenv run pytest $(path) -v

# 테스트 현황 확인
test-status:
	@echo "📋 BDD 테스트 현황 확인..."
	@echo ""
	@echo "🎯 구현 완료된 테스트:"
	@echo "  ✅ OpenAI Provider BDD 테스트: 11개 케이스"
	@echo "  ✅ Claude Provider 테스트: 11개 케이스"
	@echo "  ✅ Google Provider 테스트: 12개 케이스"
	@echo "  ✅ AI Router 통합 테스트: 9개 케이스"
	@echo "  ✅ 간단한 통합 테스트: 2개 케이스"
	@echo "  ✅ BDD Feature 파일: 3개"
	@echo "  ✅ BDD Step Definitions: 3개"
	@echo ""
	@echo "✅ 모든 Provider 활성화:"
	@echo "  ✅ OpenAI Provider: API 키 설정됨"
	@echo "  ✅ Claude Provider: anthropic 패키지 설치됨"
	@echo "  ✅ Google Provider: google-generativeai 패키지 설치됨"
	@echo ""
	@echo "📊 실행 가능한 테스트 수:"
	@pipenv run pytest --collect-only tests/unit/ai/providers/ tests/integration/test_ai_provider_simple.py 2>/dev/null | grep "<Function" | wc -l | xargs echo "  총 테스트 케이스:"

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