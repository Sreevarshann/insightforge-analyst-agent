from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from insightforge.ingest.service import describe_schema
from insightforge.profiling.engine import profile_parquet


def _profile(tmp_path: Path, table: pa.Table) -> dict[str, Any]:
    p = tmp_path / "t.parquet"
    pq.write_table(table, p)
    return profile_parquet(p, describe_schema(p))


def col(profile: dict[str, Any], name: str) -> dict[str, Any]:
    return next(c for c in profile["columns"] if c["name"] == name)


def test_numeric_statistics_match_numpy(tmp_path: Path) -> None:
    rng = np.random.default_rng(7)
    values = rng.normal(100, 15, 500)
    prof = _profile(tmp_path, pa.table({"v": values}))
    s = col(prof, "v")["numeric"]
    assert s["mean"] == pytest.approx(values.mean())
    assert s["std"] == pytest.approx(values.std(ddof=1))
    assert s["median"] == pytest.approx(np.median(values))
    assert s["p25"] == pytest.approx(np.percentile(values, 25))
    assert s["min"] == pytest.approx(values.min()) and s["max"] == pytest.approx(values.max())
    assert sum(b["count"] for b in s["histogram"]) == 500
    q1, q3 = np.percentile(values, [25, 75])
    lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    assert s["outliers"]["count"] == int(((values < lo) | (values > hi)).sum())


def test_nulls_distinct_and_duplicates(tmp_path: Path) -> None:
    t = pa.table({"a": [1, 1, 2, None], "b": ["x", "x", "y", "z"]})
    prof = _profile(tmp_path, t)
    assert prof["row_count"] == 4
    assert prof["duplicate_rows"] == 1
    a = col(prof, "a")
    assert a["null_count"] == 1 and a["missing_pct"] == 25.0 and a["distinct_count"] == 2
    assert prof["total_missing_cells"] == 1
    assert col(prof, "b")["top_values"][0] == {"value": "x", "count": 2}


def test_candidate_detection(tmp_path: Path) -> None:
    n = 200
    t = pa.table(
        {
            "customer_id": list(range(n)),
            "region": [["East", "West", "North"][i % 3] for i in range(n)],
            "signup": [f"2025-01-{(i % 28) + 1:02d}" for i in range(n)],
            "amount": [float(i) for i in range(n)],
            "tier": [i % 3 for i in range(n)],
        }
    )
    prof = _profile(tmp_path, t)
    assert "signup" in prof["candidate_date_columns"]
    assert "region" in prof["candidate_dimensions"]
    assert "tier" in prof["candidate_dimensions"]
    assert "amount" in prof["candidate_measures"]
    assert "customer_id" not in prof["candidate_measures"]  # id-like
    assert any("dates" in s["message"] for s in prof["suggestions"] if s["column"] == "signup")


def test_suggestions_flag_quality_issues(tmp_path: Path) -> None:
    t = pa.table({"c": [5] * 10, "m": [None] * 5 + [1] * 5, "s": [" a", "b "] + ["c"] * 8})
    prof = _profile(tmp_path, t)
    messages = {(s["column"], s["message"]) for s in prof["suggestions"]}
    assert ("c", "Column is constant") in messages
    assert any(c == "m" and "missing" in m for c, m in messages)
    assert any(c == "s" and "whitespace" in m for c, m in messages)


def test_empty_and_all_null_columns(tmp_path: Path) -> None:
    t = pa.table({"x": pa.array([None, None], type=pa.float64())})
    prof = _profile(tmp_path, t)
    s = col(prof, "x")["numeric"]
    assert s["mean"] is None and s["histogram"] == []


def test_profile_endpoint(client: TestClient) -> None:
    buf = io.BytesIO()
    pq.write_table(pa.table({"x": [1.0, 2.0, 3.0, 100.0]}), buf)
    ds = client.post("/api/datasets", files={"file": ("d.parquet", buf.getvalue())}).json()[0]
    prof = client.get(f"/api/datasets/{ds['id']}/profile").json()
    assert prof["row_count"] == 4 and prof["version"] == 1
    assert col(prof, "x")["numeric"]["sum"] == 106.0
