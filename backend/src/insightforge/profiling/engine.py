"""Dataset profiling. Every statistic is computed by DuckDB over the stored Parquet file."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import duckdb

from insightforge.engine.duck import locked_connection, quote_ident

NUMERIC_TYPES = (
    "TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT", "UTINYINT", "USMALLINT",
    "UINTEGER", "UBIGINT", "FLOAT", "DOUBLE", "REAL",
)  # fmt: skip
TEMPORAL_PREFIXES = ("DATE", "TIMESTAMP", "TIME")
HISTOGRAM_BINS = 20
TOP_K = 10
SAMPLE_ROWS = 10
DATE_PARSE_THRESHOLD = 0.95


def kind_of(duck_type: str) -> str:
    t = duck_type.upper()
    if t.startswith("DECIMAL") or t in NUMERIC_TYPES:
        return "numeric"
    if t.startswith(TEMPORAL_PREFIXES):
        return "temporal"
    if t == "BOOLEAN":
        return "boolean"
    if t == "VARCHAR":
        return "text"
    return "other"


def _f(v: Any) -> float | None:
    if v is None:
        return None
    fv = float(v)
    return None if math.isnan(fv) or math.isinf(fv) else fv


def profile_parquet(path: Path, schema: list[dict[str, Any]]) -> dict[str, Any]:
    con = locked_connection({"t": path})
    try:
        return _profile(con, schema)
    finally:
        con.close()


def _scalar(con: duckdb.DuckDBPyConnection, sql: str) -> Any:
    row = con.execute(sql).fetchone()
    return row[0] if row else None


def _profile(con: duckdb.DuckDBPyConnection, schema: list[dict[str, Any]]) -> dict[str, Any]:
    n = int(_scalar(con, "SELECT count(*) FROM t"))
    distinct_rows = int(_scalar(con, "SELECT count(*) FROM (SELECT DISTINCT * FROM t)"))
    columns = [_profile_column(con, c["name"], c["type"], n) for c in schema]
    sample = con.execute(f"SELECT * FROM t LIMIT {SAMPLE_ROWS}").fetchall()  # noqa: S608
    profile = {
        "row_count": n,
        "column_count": len(schema),
        "duplicate_rows": n - distinct_rows,
        "total_missing_cells": sum(c["null_count"] for c in columns),
        "columns": columns,
        "sample_rows": [[_jsonable(v) for v in r] for r in sample],
        "candidate_date_columns": [c["name"] for c in columns if c["is_date_candidate"]],
        "candidate_dimensions": [c["name"] for c in columns if c["is_dimension_candidate"]],
        "candidate_measures": [
            c["name"] for c in columns if c["kind"] == "numeric" and not c["is_id_like"]
        ],
    }
    profile["suggestions"] = cleaning_suggestions(profile)
    return profile


def _profile_column(
    con: duckdb.DuckDBPyConnection, name: str, duck_type: str, n: int
) -> dict[str, Any]:
    q = quote_ident(name)
    kind = kind_of(duck_type)
    nulls, distinct = con.execute(
        f"SELECT count(*) FILTER (WHERE {q} IS NULL), count(DISTINCT {q}) FROM t"  # noqa: S608
    ).fetchone() or (0, 0)
    col: dict[str, Any] = {
        "name": name,
        "type": duck_type,
        "kind": kind,
        "null_count": int(nulls),
        "missing_pct": round(100.0 * nulls / n, 4) if n else 0.0,
        "distinct_count": int(distinct),
        "is_id_like": False,
        "is_date_candidate": kind == "temporal",
        "is_dimension_candidate": False,
    }
    non_null = n - int(nulls)
    if kind == "numeric":
        col["numeric"] = _numeric_stats(con, q)
        int_like = duck_type.upper() in NUMERIC_TYPES[:9]
        col["is_id_like"] = bool(
            int_like and non_null > 20 and distinct == non_null and "id" in name.lower()
        )
        col["is_dimension_candidate"] = bool(int_like and 1 < distinct <= 12 and n >= 50)
    elif kind == "temporal":
        lo, hi = con.execute(f"SELECT min({q}), max({q}) FROM t").fetchone() or (None, None)  # noqa: S608
        col["temporal"] = {"min": _jsonable(lo), "max": _jsonable(hi)}
    if kind in {"text", "boolean"} or col["is_dimension_candidate"]:
        col["top_values"] = [
            {"value": _jsonable(v), "count": int(c)}
            for v, c in con.execute(
                f"SELECT {q}, count(*) c FROM t WHERE {q} IS NOT NULL "  # noqa: S608
                f"GROUP BY 1 ORDER BY c DESC, 1 LIMIT {TOP_K}"
            ).fetchall()
        ]
    if kind == "text":
        lengths = con.execute(
            f"SELECT min(length({q})), max(length({q})), "  # noqa: S608
            f"count(*) FILTER (WHERE {q} <> trim({q})) FROM t"
        ).fetchone() or (None, None, 0)
        col["text"] = {"min_length": lengths[0], "max_length": lengths[1], "untrimmed": lengths[2]}
        parsed = int(
            _scalar(con, f"SELECT count(TRY_CAST({q} AS DATE)) FROM t")  # noqa: S608
        )
        numeric_parsed = int(
            _scalar(con, f"SELECT count(TRY_CAST({q} AS DOUBLE)) FROM t")  # noqa: S608
        )
        col["is_date_candidate"] = bool(non_null and parsed / non_null >= DATE_PARSE_THRESHOLD)
        col["looks_numeric"] = bool(non_null and numeric_parsed / non_null >= DATE_PARSE_THRESHOLD)
        col["is_dimension_candidate"] = bool(
            not col["is_date_candidate"]
            and 1 < distinct <= max(50, int(0.05 * n))
            and distinct < non_null
        )
        col["is_id_like"] = bool(non_null > 20 and distinct == non_null)
    if kind == "boolean":
        col["is_dimension_candidate"] = True
    return col


def _numeric_stats(con: duckdb.DuckDBPyConnection, q: str) -> dict[str, Any]:
    row = con.execute(
        f"""SELECT min({q}), max({q}), avg({q}), stddev_samp({q}),
                   quantile_cont({q}, 0.25), median({q}), quantile_cont({q}, 0.75),
                   sum({q}), count(*) FILTER (WHERE {q} = 0)
            FROM t"""  # noqa: S608
    ).fetchone()
    assert row is not None
    lo, hi, mean, std, p25, p50, p75, total, zeros = row
    stats: dict[str, Any] = {
        "min": _f(lo),
        "max": _f(hi),
        "mean": _f(mean),
        "std": _f(std),
        "p25": _f(p25),
        "median": _f(p50),
        "p75": _f(p75),
        "sum": _f(total),
        "zero_count": int(zeros or 0),
        "histogram": [],
        "outliers": {"method": "iqr_1.5", "count": 0, "lower_fence": None, "upper_fence": None},
    }
    if p25 is not None and p75 is not None:
        iqr = float(p75) - float(p25)
        lower, upper = float(p25) - 1.5 * iqr, float(p75) + 1.5 * iqr
        count = _scalar(
            con,
            f"SELECT count(*) FROM t WHERE {q} < {lower!r} OR {q} > {upper!r}",  # noqa: S608
        )
        stats["outliers"] = {
            "method": "iqr_1.5",
            "count": int(count),
            "lower_fence": lower,
            "upper_fence": upper,
        }
    if lo is not None and hi is not None:
        stats["histogram"] = _histogram(con, q, float(lo), float(hi))
    return stats


def _histogram(
    con: duckdb.DuckDBPyConnection, q: str, lo: float, hi: float
) -> list[dict[str, Any]]:
    if hi == lo:
        c = _scalar(con, f"SELECT count({q}) FROM t")  # noqa: S608
        return [{"start": lo, "end": hi, "count": int(c)}]
    width = (hi - lo) / HISTOGRAM_BINS
    rows = con.execute(
        f"""SELECT least(floor(({q} - {lo!r}) / {width!r}), {HISTOGRAM_BINS - 1})::INT b, count(*)
            FROM t WHERE {q} IS NOT NULL GROUP BY 1 ORDER BY 1"""  # noqa: S608
    ).fetchall()
    counts = dict(rows)
    return [
        {"start": lo + i * width, "end": lo + (i + 1) * width, "count": int(counts.get(i, 0))}
        for i in range(HISTOGRAM_BINS)
    ]


def cleaning_suggestions(profile: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if profile["duplicate_rows"]:
        out.append({
            "severity": "warning",
            "column": "",
            "message": f"{profile['duplicate_rows']} fully duplicated rows",
        })  # fmt: skip
    for c in profile["columns"]:
        name = c["name"]
        if c["missing_pct"] >= 20:
            out.append({
                "severity": "warning",
                "column": name,
                "message": f"{c['missing_pct']:.1f}% of values are missing",
            })  # fmt: skip
        if profile["row_count"] > 1 and c["distinct_count"] == 1 and c["null_count"] == 0:
            out.append({"severity": "info", "column": name, "message": "Column is constant"})
        if c.get("looks_numeric"):
            out.append({
                "severity": "info",
                "column": name,
                "message": "Text column contains numeric values; consider casting",
            })  # fmt: skip
        if c["kind"] == "text" and c["is_date_candidate"]:
            out.append({
                "severity": "info",
                "column": name,
                "message": "Text column contains dates; consider casting to DATE",
            })  # fmt: skip
        if c.get("text", {}).get("untrimmed"):
            out.append({
                "severity": "info",
                "column": name,
                "message": f"{c['text']['untrimmed']} values have leading/trailing whitespace",
            })  # fmt: skip
        outliers = c.get("numeric", {}).get("outliers", {})
        if outliers.get("count"):
            out.append({
                "severity": "info",
                "column": name,
                "message": f"{outliers['count']} values outside the 1.5 x IQR fences",
            })  # fmt: skip
    return out


def _jsonable(v: Any) -> Any:
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return _f(v)
    return str(v)
