PYTHON ?= python
PIPENV ?= pipenv
DOCKER ?= docker
DOCKER_COMPOSE ?= docker-compose
UVICORN ?= uvicorn
APP = app.main:app

.PHONY: help freeze run test build run-docker stop-docker remove-docker build-compose up-compose down-compose upgrade downgrade

help: ## 사용 가능한 명령을 보여줍니다
	grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS=":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# pipenv
freeze: ## Pipenv 의존성을 requirements.txt로 내보냅니다
	$(PIPENV) requirements > requirements.txt

# fastapi
run: ## 개발 서버를 실행합니다
	$(UVICORN) $(APP) --host 0.0.0.0 --port 8002 --reload

# test
test: ## 단위 및 기능 테스트를 실행합니다
	pytest

# docker
build: ## Docker 이미지를 빌드합니다
	$(DOCKER) build -t linkyboard-ai .

run-docker: ## Docker 컨테이너를 실행합니다
	$(DOCKER) run -d -p 8001:80 --name linkyboard-ai linkyboard-ai

stop-docker: ## Docker 컨테이너를 중지합니다
	$(DOCKER) stop linkyboard-ai

remove-docker: ## Docker 컨테이너를 삭제합니다
	$(DOCKER) rm linkyboard-ai

# docker-compose
build-compose: ## docker-compose 이미지를 빌드합니다
	$(DOCKER_COMPOSE) build

up-compose: ## docker-compose 서비스를 시작합니다
	$(DOCKER_COMPOSE) up -d

down-compose: ## docker-compose 서비스를 중지합니다
	$(DOCKER_COMPOSE) down

# alembic
upgrade: ## 데이터베이스를 최신 상태로 마이그레이션합니다
	alembic upgrade head

downgrade: ## 데이터베이스 마이그레이션을 한 단계 되돌립니다
	alembic downgrade -1
