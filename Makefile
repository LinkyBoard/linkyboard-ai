# pipenv 
.PHONY: freeze
freeze:
	pipenv requirements > requirements.txt

# fastapi
.PHONY: run
run:
	uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
