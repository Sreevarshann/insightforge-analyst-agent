"""LIVE tests against a real local Ollama model. Excluded from CI (`-m "not live"`).

Run with:  uv run pytest -m live tests/test_live_agent.py -s
"""

from __future__ import annotations

import io

import httpx
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from insightforge.config import Settings
from insightforge.llm.http_providers import OllamaProvider

pytestmark = pytest.mark.live
MODEL = "qwen3:4b-instruct"


def _ollama_up() -> bool:
    try:
        tags = httpx.get("http://127.0.0.1:11434/api/tags", timeout=2).json()
        return any(m["name"] == MODEL for m in tags.get("models", []))
    except httpx.HTTPError:
        return False


@pytest.fixture
def live(client: TestClient, settings: Settings) -> TestClient:
    if not _ollama_up():
        pytest.skip(f"Ollama with {MODEL} not available")
    client.app.state.provider_factory = lambda: OllamaProvider("http://127.0.0.1:11434", MODEL, 180)  # type: ignore[attr-defined]
    rng = np.random.default_rng(3)
    n = 300
    df = pd.DataFrame(
        {
            "order_date": (pd.Timestamp("2025-01-01") + pd.to_timedelta(rng.integers(0, 365, n), "D")).date,
            "region": rng.choice(["East", "West", "North"], n),
            "revenue": rng.uniform(10, 100, n).round(2),
            "churned": rng.integers(0, 2, n),
        }
    )
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    client.post("/api/datasets", files={"file": ("orders.csv", buf.getvalue().encode())})
    client.app.state.frame = df  # type: ignore[attr-defined]
    return client


@pytest.mark.parametrize(
    ("question", "ops"),
    [
        ("What is the total revenue by region?", {"aggregate"}),
        ("Show the monthly revenue trend", {"trend", "aggregate"}),
        ("Which region has the highest churn rate?", {"rate", "aggregate"}),
    ],
)
def test_live_planner_produces_executable_plan(live: TestClient, question: str, ops: set[str]) -> None:
    a = live.post("/api/analyses", json={"question": question}).json()
    print(question, "->", a["status"], [s["op"] for s in a["steps"]], a["plan"]["attempts"], a["duration_ms"], "ms")
    assert a["status"] == "completed", a["explanation"]
    assert a["steps"][0]["op"] in ops | {"sql"}
