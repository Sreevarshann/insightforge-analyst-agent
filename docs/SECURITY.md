# Security model

InsightForge treats **uploaded files, model output, and SQL as untrusted**.

| Threat | Mitigation | Verified by |
|---|---|---|
| SQL injection / destructive SQL | SQLGlot AST policy (single read-only query, no DDL/DML/COPY/ATTACH/INSTALL/LOAD/SET/PRAGMA, registered tables only, function deny-list, no URLs); typed ops render literals via SQLGlot and quote identifiers from the stored schema | `test_sql_validator.py`, `test_ops.py` (injection in filters/group_by) |
| Arbitrary file / network access from SQL | Separate `python -I` worker under macOS `sandbox-exec` or Linux `bwrap` (no network, read-only, only the query's Parquet files readable), rlimits, locked DuckDB (`allowed_paths`, external access off, config locked, no extensions) | `test_sandbox.py`, `test_duck.py` (real subprocesses) |
| Resource exhaustion | Wall-clock timeout + kill, `RLIMIT_CPU`, DuckDB `memory_limit`, Linux `RLIMIT_AS` guard, row caps, upload size cap, XLSX decompression-size guard, column/sheet limits | `test_sandbox.py`, `test_ingest.py` |
| Arbitrary code execution | No `exec`/`eval` of model output anywhere; operations are a fixed registry with Pydantic arguments; Excel formulas are never evaluated; SQLite uploads opened read-only/immutable with `trusted_schema=OFF` | code review, `test_ops.py` (unknown op rejected) |
| Prompt injection | Model output is a *proposal*: validated against schemas/policy before anything runs; benchmark includes injection questions | `evaluation/benchmark.py`, `test_agent.py` |
| Fabricated numbers | Placeholder-only numbers + verifier (`ANALYTICAL_VERIFICATION.md`) | `test_verifier.py`, `test_agent.py` |
| Path traversal | Upload filenames reduced to basename; storage paths are server-generated ids; deletion checks the resolved parent | `test_ingest.py` |
| XSS | React escaping; reports HTML-escape all text and are served with a restrictive CSP; Plotly figures are server-built from typed configs (no JS) | `test_reports.py`, `test_charts.py` |
| CSV formula injection | Exported cells starting with `= + - @` are prefixed | `test_reports.py` |
| Error leakage | Global handler returns generic 500; parser errors never include file contents; sandbox stderr goes to server logs only | `test_ingest.py`, `test_query_api.py` |
| Secrets | `.env` git-ignored, no secret defaults, gitleaks scans full history in CI | CI `secrets` job |

## Assumptions and limitations

* Single-user local application: there is **no authentication or multi-tenancy** (by
  design for this project; see ReviewPilot for a multi-tenant SaaS). Bind the API to
  localhost (default) or put it behind an authenticating proxy.
* `sandbox-exec` is deprecated by Apple but functional; on Linux without working user
  namespaces isolation falls back to `rlimits` + locked DuckDB, and the active level is
  reported with every query result.
* The read-only PostgreSQL connector described in the original plan is **not implemented**;
  external databases are supported only by uploading SQLite files or exports.
* The Query Console loads the Monaco editor from a pinned CDN build
  (`monaco-editor@0.55.1` via `@monaco-editor/loader`) that bundles its own DOMPurify. npm
  audit flags DOMPurify advisories for that line; the npm dependency is overridden to a
  patched release, but the CDN runtime copy is not. The editor only displays the user's
  own SQL text. Self-hosting a patched Monaco build is a listed future improvement.
* The verifier cannot check qualitative statements (see `ANALYTICAL_VERIFICATION.md`).
