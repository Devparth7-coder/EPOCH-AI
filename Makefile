.PHONY: help install test run build bench lint docker clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## install backend + frontend dependencies
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

test: ## run the backend test suite
	cd backend && python -m pytest tests -q

resume: ## repair wiped deps/build, run tests, then serve on :8000
	./scripts/resume_preview.sh

check: ## repair wiped deps/build and verify, without serving
	./scripts/resume_preview.sh --check

run: ## run API (serves built SPA if frontend/dist exists)
	cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

build: ## build the React frontend
	cd frontend && npm run build

bench: ## run the labelled benchmark and refresh results
	cd backend && python benchmark/build_dataset.py && python benchmark/run_benchmark.py --persist --fit-calibration

docker: ## build and run the full stack (API + Postgres + pgvector)
	docker compose up --build

clean: ## remove local artefacts
	rm -f backend/epoch.db backend/epoch.db-wal backend/epoch.db-shm
	rm -rf frontend/dist backend/.pytest_cache
