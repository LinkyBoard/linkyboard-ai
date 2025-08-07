# pipenv 
.PHONY: freeze
freeze:
	pipenv requirements > requirements.txt

# fastapi
.PHONY: run
run:
	uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

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
