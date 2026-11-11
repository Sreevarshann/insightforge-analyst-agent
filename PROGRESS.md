# InsightForge — Progress

Records only work that has actually been done and verified.

| # | Milestone | Commit | Pushed | Checks |
|---|-----------|--------|--------|--------|
| 1 | Repository setup: FastAPI app factory, settings, JSON logging, health route | `85a8af9` | ✔ verified | ruff ✔ · mypy strict ✔ · pytest 3/3 ✔ |
| 2 | Metadata DB: SQLAlchemy models (datasets, versions, relationships, analyses, query log), Alembic migration run at startup | `87a209e` | ✔ verified | ruff ✔ · mypy ✔ · pytest 9/9 ✔ |
| 3 | Dataset ingestion: CSV/TSV/XLSX/Parquet/SQLite → canonical Parquet, versioning, magic-byte + size + zip-bomb checks, locked-down DuckDB preview API (sort/search/paginate) | `1ed1efe` | ✔ verified | ruff ✔ · mypy ✔ · pytest 35/35 ✔ |
| 4 | Profiling engine: per-column nulls/distinct/quantiles/histograms/IQR outliers, duplicates, date/dimension/measure candidates, cleaning suggestions (validated against NumPy) | `6fe3a20` | ✔ verified | ruff ✔ · mypy ✔ · pytest 41/41 ✔ |
| 5 | SQL security: SQLGlot AST policy, sandboxed worker process (macOS sandbox-exec / Linux bwrap / rlimits), locked DuckDB, audited `/api/query` + history | `e7c3a9b` | ✔ verified | ruff ✔ · mypy ✔ · pytest 90 passed, 1 skipped (Linux-only) |
| 6 | Typed operations (12): describe, missing values, aggregate, trend, group compare (Welch/MWU/ANOVA/Kruskal), rate (+Wilson CI, abnormal flag), correlation, OLS regression, cohort retention, k-means segments, outliers, Holt-Winters forecast w/ backtest. Each returns *facts* with provenance. `/api/ops` | `6cd8302` | ✔ verified | ruff ✔ · mypy ✔ · pytest 111 passed, 1 skipped |
| 7 | LLM providers (Ollama structured output, OpenAI-compatible, deterministic fixture) + LangGraph agent: catalog → plan → validate (repair loop, ≤3 attempts) → execute → inspect → explain; clarification path; persisted analyses API | `e6d960b` | ✔ verified | pytest 118 passed, 1 skipped; **live** (qwen3:4b-instruct via Ollama, 2026-11-11): 3/3 questions planned + executed on first attempt, 9.6–15.9 s |
| 8 | Numerical verifier + LLM explainer: fact placeholders, raw-number/unit/group/significance/causality checks, sentence removal, deterministic fallback | `072eb8a` | ✔ verified | pytest 143 passed, 1 skipped; live 3/3; see docs/ANALYTICAL_VERIFICATION.md for observed live behaviour |
| 9 | Plotly chart service: typed ChartConfig → server-built, Plotly-validated figures; chart node in the agent graph; Chart Studio preview/save API; raw-data charts use the op's own filtered sample | `f59cd68` | ✔ verified | pytest 154 passed, 1 skipped |
| — | CI workflow (ruff, mypy, tests, pip-audit, gitleaks history scan); sandbox isolation probe | `a5953b3` | ✔ | **CI run 42958550377: backend job FAILED on Linux** (sandbox worker terminated); secret scan passed. Investigating. |
| 10 | Synthetic demo data (Lumen Commerce, planted documented patterns), `make seed`, validated relationships API, join guard in SQL policy, sandbox stderr logging | see git log | ✔ | pytest 162 passed, 1 skipped (macOS) |

## Known limitations
- No functional features yet beyond the health endpoint.

## Next
- Fix Linux CI sandbox failure.
- Frontend (Next.js) design system.
- Read-only PostgreSQL connector (planned alongside SQL execution).
