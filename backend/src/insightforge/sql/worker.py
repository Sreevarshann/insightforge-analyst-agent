"""Sandboxed query worker. Runs as ``python -I -m insightforge.sql.worker``.

Reads one JSON request on stdin, writes one JSON response on stdout and exits. It runs
under OS resource limits (and, where available, an OS sandbox profile) applied by the
parent; this module only ever opens a locked DuckDB connection over the given files.
"""

from __future__ import annotations

import datetime as dt
import decimal
import json
import math
import sys
import time
import uuid
from pathlib import Path
from typing import Any


def _jsonable(v: Any) -> Any:
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return None if math.isnan(v) or math.isinf(v) else v
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (dt.date, dt.datetime, dt.time)):
        return v.isoformat()
    if isinstance(v, dt.timedelta):
        return v.total_seconds()
    if isinstance(v, (uuid.UUID, bytes)):
        return str(v)
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    return str(v)


def run(request: dict[str, Any]) -> dict[str, Any]:
    from insightforge.engine.duck import locked_connection

    views = {name: Path(p) for name, p in request["views"].items()}
    max_rows = int(request["max_rows"])
    started = time.perf_counter()
    con = locked_connection(
        views, memory_limit_mb=int(request["memory_mb"]), threads=int(request.get("threads", 2))
    )
    try:
        cur = con.execute(request["sql"])
        columns = [d[0] for d in cur.description or []]
        types = [str(d[1]) for d in cur.description or []]
        rows = cur.fetchmany(max_rows + 1)
    finally:
        con.close()
    truncated = len(rows) > max_rows
    return {
        "ok": True,
        "columns": columns,
        "types": types,
        "rows": [[_jsonable(v) for v in r] for r in rows[:max_rows]],
        "truncated": truncated,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def main() -> None:
    try:
        request = json.loads(sys.stdin.read())
        response = run(request)
    except Exception as exc:
        # Report the database error class + message (no tracebacks/paths).
        msg = str(exc).split("\n")[0][:500]
        response = {"ok": False, "error_type": type(exc).__name__, "error": msg}
    sys.stdout.write(json.dumps(response))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
