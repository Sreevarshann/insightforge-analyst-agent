<p align="center"><img src="docs/logo.svg" width="72" alt="InsightForge logo"></p>

<h1 align="center">InsightForge</h1>
<p align="center"><b>From data to decisions, with every number explained.</b></p>
<p align="center">An autonomous data-analysis workstation: an LLM plans the analysis, sandboxed DuckDB and vetted statistics compute it, Plotly shows it, and a verifier makes sure the prose only states numbers that were actually computed.</p>

---

## The problem

"Chat with your data" tools usually let a language model write SQL and then *narrate* the
result. That leaves three failure modes: unsafe execution, wrong analysis, and fluent prose
with numbers nobody computed. InsightForge treats the model as a **planner whose proposals
are validated**, executes everything in an **OS-level sandbox**, and **verifies every
number** in the explanation against computed facts.

## Why it's technically interesting

* **LangGraph agent with a repair loop**: catalog → plan → validate (Pydantic op schemas
  / SQLGlot AST policy, up to 3 attempts with error feedback) → execute → inspect → charts
  → explain & verify, with a clarification exit. Real progress is streamed over SSE.
* **Four-layer SQL isolation**: AST policy → separate `python -I` worker → macOS
  `sandbox-exec` / Linux `bubblewrap` (no network, read-only, only the query's Parquet
  files readable) + rlimits → locked DuckDB (`allowed_paths`, no extensions, config locked).
  Tests run real subprocesses that try to open sockets, read `$HOME` and write files.
* **12 typed statistical operations** (trend, cohort retention, rates with Wilson CIs,
  Welch / Mann-Whitney / ANOVA / Kruskal, OLS, k-means, IQR/z outliers, Holt-Winters with
  backtest…), each checked against independent pandas/SciPy/statsmodels code.
* **Fact-placeholder explanations**: the model writes `{{a3}}`, the verifier renders the
  exact value and removes sentences with unverified numbers, wrong units, mismatched group
  labels, unsupported significance claims or causal wording.
* **Server-built Plotly charts** from typed configs, validated by Plotly's schema; a Chart
  Studio re-renders and saves views.

## Screenshots

All screenshots are real captures of the running app (`make screenshots`) on the
**synthetic** demo data, with the local `qwen3:4b-instruct` model.

| | |
|---|---|
| ![Landing](docs/screenshots/01-landing.png) | ![Dataset overview](docs/screenshots/02-dataset-overview.png) |
| ![Schema inspector](docs/screenshots/03-schema-inspector.png) | ![Copilot](docs/screenshots/04-copilot-trend.png) |
| ![Chart Studio](docs/screenshots/05-chart-studio.png) | ![Trace](docs/screenshots/06-trace.png) |
| ![Query console](docs/screenshots/07-query-console.png) | ![Evaluation](docs/screenshots/08-evaluation.png) |

<p align="center"><img src="docs/screenshots/09-mobile-datasets.png" width="260" alt="Mobile layout"></p>

## Architecture

```mermaid
flowchart LR
  UI[Next.js 16 UI] -- REST + SSE --> API[FastAPI]
  API --> AG[LangGraph agent]
  AG -- plan / explain --> LLM[[Ollama · OpenAI-compatible · fixture]]
  AG --> OPS[Typed operations]
  OPS --> POL[SQLGlot policy]
  AG -- model SQL --> POL
  POL --> SBX[Sandboxed worker<br/>locked DuckDB]
  SBX -.-> PQ[(Versioned Parquet)]
  AG --> CH[Plotly builder]
  AG --> VER[Number verifier]
  API --> META[(SQLite + Alembic)]
```

Details: [ARCHITECTURE](docs/ARCHITECTURE.md) · [QUERY SECURITY](docs/QUERY_SECURITY.md) ·
[VERIFICATION](docs/ANALYTICAL_VERIFICATION.md) · [CHARTS](docs/CHART_ARCHITECTURE.md) ·
[DATA MODEL](docs/DATA_MODEL.md) · [API](docs/API.md) · [SECURITY](docs/SECURITY.md) ·
[TESTING](docs/TESTING.md) · [EVALUATION](docs/EVALUATION.md) · [DEMO](docs/DEMO.md) ·
[DEPLOYMENT](docs/DEPLOYMENT.md) · [DECISIONS](docs/DECISIONS.md)

## Main workflows

1. **Ingest**: CSV, TSV, XLSX (per sheet), Parquet, SQLite (per table) → validated,
   versioned, hashed Parquet + a real profile (nulls, distincts, quantiles, histograms,
   outliers, duplicates, role detection, cleaning suggestions).
2. **Explore**: Dataset Explorer with schema inspector, distributions, server-side
   searchable preview, version history, dataset comparison, validated relationships.
3. **Ask**: Analysis Copilot (3 panes) with streamed stages, verified answer, charts,
   result tables, clarification flow; inspector with facts, checks, removed sentences,
   executed SQL, node timings and the raw plan.
4. **Query**: Query Console (Monaco) for direct read-only SQL with a full audit log.
5. **Keep**: save analyses; export HTML / Markdown reports and CSV tables.

## Technology

**Backend**: Python 3.13, FastAPI (native SSE), Pydantic 2, LangGraph 1.2, DuckDB 2,
SQLGlot, pandas, Polars-ready Arrow pipeline, NumPy, SciPy, scikit-learn, statsmodels,
SQLAlchemy 2 + Alembic, Plotly. **LLM**: Ollama (`qwen3:4b-instruct`, JSON-schema
constrained output), OpenAI-compatible adapter, deterministic fixture.
**Frontend**: Next.js 16, React 19, TypeScript (strict), Tailwind 4, Radix UI,
TanStack Query, Motion, Plotly.js, Monaco, Lucide. **Quality**: ruff, mypy `--strict`,
pytest, ESLint, Vitest, Playwright, GitHub Actions, pip-audit, npm audit, gitleaks.

## Evaluation (real, measured)

13 questions over the synthetic data; expected answers recomputed with pandas at run time.

| Metric | qwen3:4b-instruct (local) | fixture heuristic |
|---|---|---|
| Numerical correctness | 66.7% (6/9) | 88.9% |
| Execution success | 77.8% | 100% |
| Clarification / injection safety / unsafe-SQL rejection | 100% / 100% / 100% | 100% / 100% / 100% |
| Median latency | 27.4 s | 0.2 s |

Small sample, small local model; see [EVALUATION](docs/EVALUATION.md) for the failure
analysis. The fixture is a keyword heuristic used to test the pipeline, not an LLM.

## Local setup

Requirements: Python 3.13 + [uv](https://docs.astral.sh/uv/), Node 24, optional
[Ollama](https://ollama.com) with `ollama pull qwen3:4b-instruct`.

```bash
make setup          # backend deps (uv sync)
make install-web    # frontend deps (npm ci)
make seed           # load SYNTHETIC demo datasets
make dev-api        # http://127.0.0.1:8111  (OpenAPI at /docs)
make dev-web        # http://127.0.0.1:3101
```

Without Ollama, set `INSIGHTFORGE_LLM_PROVIDER=fixture` in `backend/.env` (see
`.env.example`). Docker: `make up` (project `insightforge`, ports 8111/3101).

| Command | Purpose |
|---|---|
| `make test` / `make test-live` | Backend tests (CI-safe) / live model tests |
| `make lint` · `make typecheck` · `make test-web` | Static checks and frontend unit tests |
| `make e2e` | Playwright on an isolated stack (8191/3191, fixture provider) |
| `make evaluate` · `make evaluate-fixture` | Benchmark |
| `make screenshots` | Re-capture README screenshots from the running dev stack |

## Security model

Untrusted inputs: uploads, SQL, and all model output. Highlights: AST-validated read-only
SQL, OS-sandboxed execution, no `exec` of generated code, typed operations only,
verifier-gated prose, escaped reports with CSP, CSV formula neutralisation, generic error
responses, secrets scanning. Full threat table: [SECURITY.md](docs/SECURITY.md).

## Known limitations

* Single-user local app: no authentication or multi-tenancy.
* Read-only PostgreSQL connector not implemented (upload SQLite/exports instead); no PDF
  export (HTML/Markdown/CSV/PNG only).
* The verifier checks numbers, units, groups, significance and causal wording, not
  arbitrary qualitative claims.
* A 4B local model plans ~67% of benchmark questions correctly and takes ~30 s per
  answer; larger models via the OpenAI-compatible adapter were not evaluated.
* Linux isolation falls back to rlimits + locked DuckDB where user namespaces are
  unavailable (reported per query). Process-per-query adds ~100-300 ms per statement.
* Monaco runtime is loaded from a pinned CDN build (see SECURITY.md).

## Future improvements

Warm sandbox worker pool; read-only PostgreSQL connector with role checks; larger-model
evaluation; join-aware typed operations; linked cross-filtering between charts; PDF
reports; self-hosted Monaco.

---
<sub>Demo data is synthetic and fictional. InsightForge never fabricates analytical numbers.</sub>
