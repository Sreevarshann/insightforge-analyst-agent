# Query security

InsightForge executes SQL written by an LLM (or a user). That SQL is treated as
**untrusted input**. Four independent layers stand between it and the host.

| Layer | Where | What it enforces |
|---|---|---|
| 1. AST policy | `sql/validator.py` | Exactly one statement; root must be a query (`SELECT`/`WITH`/set ops); no DDL/DML/`COPY`/`ATTACH`/`INSTALL`/`LOAD`/`SET`/`PRAGMA` anywhere in the tree; no table functions in `FROM`; no schema/catalog qualification; only registered dataset tables (and CTEs); deny-list of file/network/system functions (`read_*`, `*_scan`, `glob`, `getenv`, `query`, `duckdb_*`, …); no URL literals; 20k character cap. |
| 2. Separate process | `sql/sandbox.py` | `python -I` worker with an empty environment, cwd `/`, JSON over stdin/stdout. A crash, hang or memory blow-up cannot take the API down. |
| 3. OS limits & sandbox | `sql/sandbox.py` | `RLIMIT_CPU`, `RLIMIT_FSIZE=0` (no file writes), `RLIMIT_NOFILE`, no core dumps, wall-clock timeout + kill. **macOS:** `sandbox-exec` profile – network denied, all writes denied, reads of `/Users`, `/Volumes` and per-user temp dirs denied except the Python runtime, this package and the query's Parquet files. **Linux:** `bwrap --unshare-all` (incl. network) with read-only binds and a read-only root (only a private `/tmp` tmpfs is writable) when bubblewrap works, plus an `RLIMIT_AS` runaway guard (DuckDB `memory_limit` + 3 GB, because DuckDB reserves far more virtual memory than it uses). |
| 4. Locked DuckDB | `engine/duck.py` | In-memory DB, one view per registered Parquet file, `allowed_paths` = those files, `enable_external_access=false`, extension install/autoload disabled, `lock_configuration=true`, `memory_limit`, bounded threads. |

Every submitted statement — accepted or rejected, with the reason — is written to the
`query_log` table and exposed at `GET /api/query/history`.

## What is verified by tests

* `tests/test_sql_validator.py` — 30+ accepted/rejected statements, including CTE smuggling.
* `tests/test_duck.py` — DuckDB layer alone blocks other files, `INSTALL`, `COPY TO`, `SET`.
* `tests/test_sandbox.py` (real subprocesses, nothing mocked) — runaway query killed by
  the timeout; file read via `read_csv` fails *even with the validator bypassed*; low
  memory limit surfaces as an error; on macOS the profile blocks outbound sockets, reading
  a file in `$HOME`, reading an unregistered file next to the dataset, and writing to `/tmp`.

## Known limitations (honest)

* `sandbox-exec` is deprecated by Apple, although still shipped and functional on macOS 26.
* On macOS `RLIMIT_AS` is not enforced by the kernel; memory is bounded by DuckDB's
  `memory_limit` instead.
* On Linux without bubblewrap (e.g. an unprivileged container that forbids user
  namespaces), isolation falls back to `rlimits` + locked DuckDB. The API reports the
  active level in every result (`isolation` field) so this is never silent. For production
  the worker should run in its own container with `network_mode: none`, a read-only
  dataset mount and cgroup memory/CPU limits.
