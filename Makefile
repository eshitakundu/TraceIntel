.PHONY: install backend frontend check test lint typecheck build
install:
	uv sync --locked
	cd frontend && npm ci
backend:
	uv run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
frontend:
	cd frontend && npm run dev -- --host 127.0.0.1
lint:
	uv run ruff check backend
	uv run ruff format --check backend
	cd frontend && npm run lint
typecheck:
	uv run mypy
	cd frontend && npm run typecheck
test:
	uv run pytest
	cd frontend && npm test
build:
	cd frontend && npm run build
check: lint typecheck test build