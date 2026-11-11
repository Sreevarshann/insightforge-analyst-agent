# InsightForge — Progress

Records only work that has actually been done and verified.

| # | Milestone | Commit | Pushed | Checks |
|---|-----------|--------|--------|--------|
| 1 | Repository setup: FastAPI app factory, settings, JSON logging, health route | `85a8af9` | ✔ verified | ruff ✔ · mypy strict ✔ · pytest 3/3 ✔ |
| 2 | Metadata DB: SQLAlchemy models (datasets, versions, relationships, analyses, query log), Alembic migration run at startup | `87a209e` | ✔ verified | ruff ✔ · mypy ✔ · pytest 9/9 ✔ |
| 3 | Dataset ingestion: CSV/TSV/XLSX/Parquet/SQLite → canonical Parquet, versioning, magic-byte + size + zip-bomb checks, locked-down DuckDB preview API (sort/search/paginate) | `1ed1efe` | ✔ verified | ruff ✔ · mypy ✔ · pytest 35/35 ✔ |
| 4 | Profiling engine: per-column nulls/distinct/quantiles/histograms/IQR outliers, duplicates, date/dimension/measure candidates, cleaning suggestions (validated against NumPy) | see git log | ✔ | ruff ✔ · mypy ✔ · pytest 41/41 ✔ |

## Known limitations
- No functional features yet beyond the health endpoint.

## Next
- Milestone 5: SQL AST validation + sandboxed execution worker.
- Read-only PostgreSQL connector (planned alongside SQL execution).
