# InsightForge — Plan

## Architecture (target)

- **backend/** — FastAPI + Pydantic. Metadata in SQLite (SQLAlchemy), analytical data in DuckDB.
  - `ingest/` CSV, TSV, XLSX, Parquet, SQLite; read-only PostgreSQL connector.
  - `profiling/` real per-column statistics.
  - `sql/` SQLGlot AST validation → execution in a separate sandboxed worker process
    (resource limits, no network, DuckDB external access disabled, timeouts, row caps).
  - `ops/` typed statistical operations (describe, group compare, trend, correlation, cohort,
    segmentation, outliers, regression, forecast) with validated arguments — no `exec()`.
  - `agent/` LangGraph state machine: understand → resolve schema → plan → execute → inspect →
    verify numbers → chart → explain. Ollama / OpenAI-compatible / deterministic fixture providers.
  - `verify/` checks every number in the explanation against computed results.
  - `charts/` validated Plotly JSON spec builder (no LLM-supplied JavaScript).
  - `reports/` Markdown / HTML / CSV export.
- **frontend/** — Next.js + TypeScript + Tailwind + Radix + Plotly + TanStack Query/Table + Motion.
  Graphite / aurora-lime identity. Dataset Explorer, Analysis Copilot (3-pane), Chart Studio,
  Report Builder.
- **eval/** — benchmark questions with known answers computed from the synthetic dataset.

## Milestones

1. Repository setup ✔
2. Metadata DB and configuration ✔
3. Dataset ingestion
4. Profiling engine
5. SQL validation + sandboxed execution
6. Statistical operations
7. LLM providers + agent planner
8. Numerical verifier
9. Plotly chart service
10. Frontend design system
11. Dataset Explorer
12. Analysis workspace + streaming
13. Saved analyses, reports, exports
14. Evaluation suite
15. E2E tests, screenshots, docs
16. CI and security review

Ports: API 8111, frontend 3101 (verified free on 2026-11-10).
