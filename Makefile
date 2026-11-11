# InsightForge developer commands. Backend: uv + FastAPI (port 8111).
BACKEND := backend

.PHONY: setup dev-api test lint typecheck fmt

setup:
	cd $(BACKEND) && uv sync

dev-api:
	cd $(BACKEND) && uv run uvicorn insightforge.main:app --reload --host 127.0.0.1 --port 8111

test:
	cd $(BACKEND) && uv run pytest -m "not live"

lint:
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check .

typecheck:
	cd $(BACKEND) && uv run mypy

fmt:
	cd $(BACKEND) && uv run ruff format . && uv run ruff check --fix .
