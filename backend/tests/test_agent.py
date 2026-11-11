from __future__ import annotations

import io
from typing import Any

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from insightforge.llm.base import LLMUsage


@pytest.fixture
def loaded(client: TestClient) -> TestClient:
    rng = np.random.default_rng(1)
    n = 400
    df = pd.DataFrame(
        {
            "customer_id": np.arange(n),
            "order_date": (
                pd.Timestamp("2025-01-01") + pd.to_timedelta(rng.integers(0, 360, n), "D")
            ).date,
            "region": rng.choice(["East", "West"], n),
            "plan": rng.choice(["Starter", "Pro", "Enterprise"], n),
            "revenue": rng.uniform(10, 100, n).round(2),
            "churned": rng.integers(0, 2, n),
        }
    )
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    assert (
        client.post(
            "/api/datasets", files={"file": ("orders.csv", buf.getvalue().encode())}
        ).status_code
        == 201
    )
    client.app.state.frame = df  # type: ignore[attr-defined]
    return client


def ask(client: TestClient, q: str) -> dict[str, Any]:
    res = client.post("/api/analyses", json={"question": q})
    assert res.status_code == 201, res.text
    return res.json()


def test_end_to_end_revenue_by_region(loaded: TestClient) -> None:
    a = ask(loaded, "What is total revenue by region?")
    assert a["status"] == "completed", a
    assert a["model_name"] == "fixture:fixture-heuristic-v1"
    step = a["steps"][0]
    assert step["op"] == "aggregate" and step["args"]["group_by"] == ["region"]
    df = loaded.app.state.frame  # type: ignore[attr-defined]
    got = {r[0]: r[1] for r in step["tables"][0]["rows"]}
    assert got["East"] == pytest.approx(df[df.region == "East"].revenue.sum())
    assert a["dataset_versions"] and a["plan"]["trace"][0]["node"] == "catalog"


def test_churn_question_uses_rate(loaded: TestClient) -> None:
    a = ask(loaded, "Which plan has the highest churned rate?")
    assert a["steps"][0]["op"] == "rate"


def test_clarification_when_nothing_matches(loaded: TestClient) -> None:
    a = ask(loaded, "Tell me something interesting about weather patterns")
    assert a["status"] == "needs_clarification" and "measure" in a["explanation"]


class ScriptedProvider:
    """Returns a fixed sequence of plans: used to test validation/repair behaviour."""

    name, model = "scripted", "scripted-v1"

    def __init__(self, plans: list[dict[str, Any]]) -> None:
        self.plans, self.usage, self.seen_errors = list(plans), LLMUsage(), []  # type: ignore[var-annotated]

    def complete_json(
        self, *, task: str, system: str, user: str, schema: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.usage.calls += 1
        self.seen_errors.append(payload.get("errors", []))
        return (
            self.plans.pop(0)
            if self.plans
            else {"needs_clarification": False, "assumptions": [], "steps": []}
        )


def _with(client: TestClient, provider: ScriptedProvider) -> None:
    client.app.state.provider_factory = lambda: provider  # type: ignore[attr-defined]


def test_invalid_plan_is_repaired_with_feedback(loaded: TestClient) -> None:
    bad = {
        "needs_clarification": False,
        "assumptions": [],
        "steps": [
            {
                "tool": "op",
                "purpose": "x",
                "args": {"op": "aggregate", "dataset": "orders", "measure": "profit"},
            }
        ],
    }
    good = {
        "needs_clarification": False,
        "assumptions": [],
        "steps": [
            {
                "tool": "op",
                "purpose": "x",
                "args": {"op": "aggregate", "dataset": "orders", "measure": "revenue"},
            }
        ],
    }
    p = ScriptedProvider([bad, good])
    _with(loaded, p)
    a = ask(loaded, "total profit?")
    assert a["status"] == "completed" and a["plan"]["attempts"] == 2
    assert any("profit" in e for e in p.seen_errors[1])


def test_unsafe_sql_from_model_is_never_executed(loaded: TestClient) -> None:
    evil = {
        "needs_clarification": False,
        "assumptions": [],
        "steps": [{"tool": "sql", "purpose": "x", "sql": "SELECT * FROM read_csv('/etc/passwd')"}],
    }
    p = ScriptedProvider([evil, evil, evil])
    _with(loaded, p)
    a = ask(loaded, "anything")
    assert a["status"] == "failed" and a["plan"]["attempts"] == 3
    hist = loaded.get("/api/query/history").json()
    assert all("passwd" not in h["sql"] or not h["accepted"] for h in hist)


def test_model_sql_executes_through_sandbox(loaded: TestClient) -> None:
    plan = {
        "needs_clarification": False,
        "assumptions": [],
        "steps": [
            {
                "tool": "sql",
                "purpose": "count",
                "sql": "SELECT region, count(*) AS n FROM orders GROUP BY region ORDER BY region",
            }
        ],
    }
    _with(loaded, ScriptedProvider([plan]))
    a = ask(loaded, "orders per region")
    assert a["status"] == "completed"
    assert a["steps"][0]["op"] == "sql" and a["steps"][0]["facts"]


def test_analysis_history_is_persisted(loaded: TestClient) -> None:
    a = ask(loaded, "What is total revenue by region?")
    got = loaded.get(f"/api/analyses/{a['id']}").json()
    assert got["steps"] == a["steps"]
    assert loaded.get("/api/analyses").json()[0]["id"] == a["id"]
