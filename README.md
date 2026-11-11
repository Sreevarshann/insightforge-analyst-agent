# InsightForge

**From data to decisions, with every number explained.**

InsightForge is an autonomous data-analysis workstation: upload a dataset (or connect an approved
read-only database), ask a question in plain language, and get validated SQL, typed statistical
operations, interactive Plotly charts and an explanation whose every number is traced back to an
actual computation.

> **Status: early development.** This README is expanded as features land. See
> [PLAN.md](PLAN.md) for the roadmap and [PROGRESS.md](PROGRESS.md) for what is actually done.

## Quick start (backend)

```bash
make setup      # uv sync
make test       # unit tests (no LLM required)
make dev-api    # http://127.0.0.1:8111/api/health
```

Requirements: Python 3.13, [uv](https://docs.astral.sh/uv/). A local [Ollama](https://ollama.com)
model is optional for development and never required by tests.
