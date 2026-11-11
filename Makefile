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

.PHONY: test-live
# Requires a running Ollama with qwen3:4b-instruct pulled.
test-live:
	cd $(BACKEND) && uv run pytest -m live -s

.PHONY: seed demo-data
# Generate the SYNTHETIC Lumen Commerce CSVs and load them as demo datasets.
seed:
	cd $(BACKEND) && uv run python -m insightforge.demo.seed

demo-data:
	cd $(BACKEND) && uv run python -m insightforge.demo.generate --out ../demo-data

.PHONY: evaluate evaluate-fixture e2e screenshots test-web
# Benchmark against the real local model (writes eval/results/latest-ollama-*.json).
evaluate:
	cd $(BACKEND) && uv run python -m insightforge.evaluation.benchmark --provider ollama --model qwen3:4b-instruct --out ../eval/results

# Deterministic pipeline benchmark (fixture heuristic, not an LLM).
evaluate-fixture:
	cd $(BACKEND) && uv run python -m insightforge.evaluation.benchmark --provider fixture --out ../eval/results

test-web:
	cd frontend && npm run lint && npm run typecheck && npm test

# Isolated stack on ports 8191/3191 with the fixture provider and fresh synthetic data.
e2e:
	cd frontend && npx playwright test

# Requires `make dev-api` + `make dev-web` running with the real model.
screenshots:
	cd frontend && SCREENSHOT_BASE_URL=http://127.0.0.1:3101 npx playwright test

.PHONY: dev-web install-web
install-web:
	cd frontend && npm ci

dev-web:
	cd frontend && npm run dev -- --port 3101
