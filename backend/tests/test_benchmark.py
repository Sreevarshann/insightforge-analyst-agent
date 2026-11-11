from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from insightforge.evaluation.benchmark import CASES, run_benchmark
from insightforge.llm.fixture import FixtureProvider


def test_fixture_benchmark_runs_end_to_end(tmp_path: Path) -> None:
    subset = [
        c for c in CASES if c.id in {"revenue_by_region", "churn_by_plan", "weather", "inject_drop"}
    ]
    report = run_benchmark(FixtureProvider, label="fixture-test", out_dir=tmp_path, cases=subset)
    s = report["summary"]
    assert s["cases"] == 4
    assert s["policy_rejection"] == 1.0  # deterministic: every unsafe statement rejected
    assert s["injection_safe"] == 1.0
    assert s["numerical_correct"] == 1.0  # expected values recomputed with pandas
    assert (tmp_path / "latest-fixture-test.json").is_file()


def test_evaluation_endpoint_lists_latest_reports(tmp_path: Path) -> None:
    from insightforge.config import Settings
    from insightforge.main import create_app

    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "latest-x.json").write_text(
        '{"summary": {"label": "x"}, "cases": [], "policy": []}'
    )
    s = Settings(environment="test", data_dir=tmp_path / "v", eval_results_dir=tmp_path / "r")
    with TestClient(create_app(s)) as c:
        assert c.get("/api/evaluation").json()[0]["summary"]["label"] == "x"
