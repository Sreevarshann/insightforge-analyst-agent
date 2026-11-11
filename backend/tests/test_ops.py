"""Operations are checked against independent pandas / SciPy / statsmodels computations."""

from __future__ import annotations

import io
from typing import Any

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from scipy import stats


@pytest.fixture
def frame() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = 1200
    dates = pd.to_datetime("2024-01-01") + pd.to_timedelta(rng.integers(0, 730, n), unit="D")
    region = rng.choice(["East", "West", "North"], n, p=[0.5, 0.3, 0.2])
    discount = rng.uniform(0, 0.3, n).round(3)
    revenue = (100 + 50 * (region == "West") + 200 * discount + rng.normal(0, 10, n)).round(2)
    churned = (rng.uniform(0, 1, n) < np.where(region == "North", 0.4, 0.1)).astype(int)
    return pd.DataFrame(
        {
            "customer_id": rng.integers(1, 300, n),
            "order_date": dates.date,
            "region": region,
            "discount": discount,
            "revenue": revenue,
            "churned": churned,
        }
    )


@pytest.fixture
def loaded(client: TestClient, frame: pd.DataFrame) -> TestClient:
    buf = io.StringIO()
    frame.to_csv(buf, index=False)
    res = client.post("/api/datasets", files={"file": ("orders.csv", buf.getvalue().encode())})
    assert res.status_code == 201, res.text
    return client


def run(client: TestClient, **body: Any) -> dict[str, Any]:
    res = client.post("/api/ops/run", json={"dataset": "orders", **body})
    assert res.status_code == 200, res.text
    return res.json()


def fact(result: dict[str, Any], label: str) -> Any:
    return next(f["value"] for f in result["facts"] if f["label"] == label)


def test_aggregate_by_region_matches_pandas(loaded: TestClient, frame: pd.DataFrame) -> None:
    r = run(loaded, op="aggregate", measure="revenue", agg="sum", group_by=["region"])
    expected = frame.groupby("region")["revenue"].sum()
    got = {row[0]: row[1] for row in r["tables"][0]["rows"]}
    for k, v in expected.items():
        assert got[k] == pytest.approx(v)
    assert fact(r, "total sum(revenue)") == pytest.approx(frame["revenue"].sum())
    share = fact(r, "share of total sum(revenue) for region=East")
    assert share == pytest.approx(100 * expected["East"] / expected.sum())
    assert r["sql"] and r["query_ids"] and r["chart_hint"]["type"] == "bar"


def test_aggregate_with_filters_and_time_grain(loaded: TestClient, frame: pd.DataFrame) -> None:
    r = run(
        loaded,
        op="aggregate",
        agg="count",
        date_column="order_date",
        time_grain="quarter",
        filters=[{"column": "region", "op": "in", "value": ["West"]}],
    )
    f = frame[frame.region == "West"]
    q = pd.to_datetime(f["order_date"]).dt.to_period("Q").value_counts().sort_index()
    rows = r["tables"][0]["rows"]
    assert [row[1] for row in rows] == list(q.values)


def test_trend_growth_matches_pandas(loaded: TestClient, frame: pd.DataFrame) -> None:
    r = run(loaded, op="trend", measure="revenue", date_column="order_date", grain="month")
    m = (
        frame.assign(p=pd.to_datetime(frame.order_date).dt.to_period("M"))
        .groupby("p")["revenue"]
        .sum()
    )
    rows = r["tables"][0]["rows"]
    assert [row[1] for row in rows] == pytest.approx(list(m.values))
    growth = m.pct_change() * 100
    assert rows[5][2] == pytest.approx(growth.iloc[5])


def test_trend_flags_incomplete_final_period(client: TestClient) -> None:
    csv = b"d,v\n2025-01-05,1\n2025-02-03,2\n2025-03-10,3\n"
    client.post("/api/datasets", files={"file": ("s.csv", csv)})
    r = client.post(
        "/api/ops/run", json={"dataset": "s", "op": "trend", "measure": "v", "date_column": "d"}
    ).json()
    assert any("incomplete" in n for n in r["notes"])


def test_group_compare_pvalue_matches_scipy(loaded: TestClient, frame: pd.DataFrame) -> None:
    r = run(
        loaded,
        op="group_compare",
        measure="revenue",
        group_column="region",
        groups=["East", "West"],
    )
    e, w = frame[frame.region == "East"].revenue, frame[frame.region == "West"].revenue
    expected = stats.ttest_ind(e, w, equal_var=False).pvalue
    assert fact(r, "Welch t-test p-value") == pytest.approx(expected, rel=1e-6)
    assert any("causation" in n for n in r["notes"])


def test_rate_by_region(loaded: TestClient, frame: pd.DataFrame) -> None:
    r = run(loaded, op="rate", outcome="churned", group_by=["region"])
    expected = frame.groupby("region")["churned"].mean() * 100
    assert fact(r, "churned rate for region=North") == pytest.approx(expected["North"])
    rows = r["tables"][0]["rows"]
    assert rows[0][0] == "North"  # highest churn first
    assert fact(r, "overall churned rate") == pytest.approx(frame.churned.mean() * 100)


def test_rate_rejects_non_binary(loaded: TestClient) -> None:
    res = loaded.post(
        "/api/ops/run", json={"dataset": "orders", "op": "rate", "outcome": "revenue"}
    )
    assert res.status_code == 422 and "binary" in res.text


def test_correlation_matches_scipy(loaded: TestClient, frame: pd.DataFrame) -> None:
    r = run(loaded, op="correlation", columns=["discount", "revenue"])
    exp = stats.pearsonr(frame.discount, frame.revenue)
    assert fact(r, "pearson correlation between discount and revenue") == pytest.approx(
        exp.statistic
    )
    s = run(loaded, op="correlation", columns=["discount", "revenue"], method="spearman")
    assert fact(s, "spearman correlation between discount and revenue") == pytest.approx(
        stats.spearmanr(frame.discount, frame.revenue).statistic
    )


def test_regression_recovers_coefficient(loaded: TestClient, frame: pd.DataFrame) -> None:
    import statsmodels.api as sm

    r = run(loaded, op="regression", target="revenue", features=["discount"])
    model = sm.OLS(frame.revenue, sm.add_constant(frame[["discount"]])).fit()
    assert fact(r, "coefficient of discount on revenue") == pytest.approx(model.params["discount"])
    assert fact(r, "R-squared") == pytest.approx(model.rsquared)


def test_cohort_retention_matches_pandas(loaded: TestClient, frame: pd.DataFrame) -> None:
    r = run(
        loaded,
        op="cohort_retention",
        entity_column="customer_id",
        date_column="order_date",
        max_periods=3,
    )
    f = frame.assign(p=pd.to_datetime(frame.order_date).dt.to_period("M"))
    first = f.groupby("customer_id")["p"].min().rename("c")
    f = f.join(first, on="customer_id")
    f["k"] = (f.p - f.c).apply(lambda x: x.n)
    cohort = f.c.min()
    sub = f[f.c == cohort]
    size = sub.customer_id.nunique()
    ret1 = 100 * sub[sub.k == 1].customer_id.nunique() / size
    row = r["tables"][0]["rows"][0]
    assert row[1] == size and row[3] == pytest.approx(ret1)


def test_segment_is_deterministic(loaded: TestClient) -> None:
    a = run(loaded, op="segment", features=["revenue", "discount"], k=3)
    b = run(loaded, op="segment", features=["revenue", "discount"], k=3)
    assert a["tables"][0]["rows"] == b["tables"][0]["rows"]
    assert sum(r[1] for r in a["tables"][0]["rows"]) == 1200
    assert -1 <= fact(a, "silhouette score") <= 1


def test_outliers_iqr_matches_pandas(loaded: TestClient, frame: pd.DataFrame) -> None:
    r = run(loaded, op="outliers", column="revenue")
    q1, q3 = frame.revenue.quantile([0.25, 0.75])
    iqr = q3 - q1
    expected = ((frame.revenue < q1 - 1.5 * iqr) | (frame.revenue > q3 + 1.5 * iqr)).sum()
    assert fact(r, "outliers in revenue") == expected


def test_forecast_runs_with_backtest(loaded: TestClient) -> None:
    r = run(loaded, op="forecast", measure="revenue", date_column="order_date", horizon=3)
    kinds = [row[2] for row in r["tables"][0]["rows"]]
    assert kinds.count("forecast") == 3
    assert any(f["label"] == "backtest MAE" for f in r["facts"])


def test_describe_and_missing(loaded: TestClient, frame: pd.DataFrame) -> None:
    d = run(loaded, op="describe", columns=["revenue"])
    assert fact(d, "mean of revenue") == pytest.approx(frame.revenue.mean())
    m = run(loaded, op="missing_values")
    assert fact(m, "rows with any missing value") == 0


@pytest.mark.parametrize(
    ("body", "fragment"),
    [
        ({"op": "aggregate", "measure": "nope"}, "does not exist"),
        ({"op": "aggregate", "measure": "region", "agg": "sum"}, "expected"),
        (
            {
                "op": "aggregate",
                "measure": "revenue",
                "filters": [{"column": "region", "op": "=", "value": {"$ne": 1}}],
            },
            "scalar",
        ),
        ({"op": "exec_python", "code": "import os"}, "op"),
        (
            {
                "op": "aggregate",
                "measure": "revenue",
                "group_by": ['region"; DROP TABLE orders; --'],
            },
            "does not exist",
        ),
    ],
)
def test_invalid_operation_arguments_rejected(
    loaded: TestClient, body: dict[str, Any], fragment: str
) -> None:
    res = loaded.post("/api/ops/run", json={"dataset": "orders", **body})
    assert res.status_code == 422 and fragment in res.text


def test_filter_values_are_literals_not_sql(loaded: TestClient) -> None:
    r = run(
        loaded,
        op="aggregate",
        agg="count",
        filters=[{"column": "region", "op": "=", "value": "East' OR '1'='1"}],
    )
    assert r["tables"][0]["rows"][0][0] == 0


def test_operation_queries_are_audited(loaded: TestClient) -> None:
    run(loaded, op="aggregate", measure="revenue")
    hist = loaded.get("/api/query/history").json()
    assert hist[0]["origin"] == "agent" and hist[0]["accepted"]
