from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from insightforge.charts.builder import (
    ChartConfig,
    ChartError,
    build_figure,
    suggest_config,
    validate_spec,
)

TABLE = {
    "name": "result",
    "columns": ["region", "period", "value"],
    "rows": [
        ["East", "2025-01-01", 10],
        ["West", "2025-01-01", 5],
        ["East", "2025-02-01", 12],
        ["West", "2025-02-01", 7],
    ],
}


def test_bar_chart_values_come_from_table() -> None:
    fig = build_figure(
        ChartConfig(type="bar", x="region", y="value"), [{**TABLE, "rows": TABLE["rows"][:2]}]
    )["figure"]
    assert fig["data"][0]["type"] == "bar"
    assert fig["data"][0]["x"] == ["East", "West"] and fig["data"][0]["y"] == [10, 5]
    assert "template" not in fig["layout"]


def test_line_with_color_creates_one_trace_per_group() -> None:
    fig = build_figure(ChartConfig(type="line", x="period", y="value", color="region"), [TABLE])[
        "figure"
    ]
    assert [t["name"] for t in fig["data"]] == ["East", "West"]
    assert fig["data"][0]["y"] == [10, 12]


def test_stacked_bar_and_category_filter() -> None:
    fig = build_figure(
        ChartConfig(
            type="stacked_bar", x="period", y="value", color="region", category_filter=["West"]
        ),
        [TABLE],
    )["figure"]
    assert fig["layout"]["barmode"] == "stack" and len(fig["data"]) == 1


def test_top_n_limits_bars() -> None:
    rows = [[f"c{i}", "x", i] for i in range(100)]
    fig = build_figure(
        ChartConfig(type="bar", x="region", y="value", top_n=10), [{**TABLE, "rows": rows}]
    )["figure"]
    assert len(fig["data"][0]["x"]) == 10 and fig["data"][0]["y"][0] == 99


def test_heatmap_and_forecast() -> None:
    matrix = {
        "name": "matrix",
        "columns": ["column", "a", "b"],
        "rows": [["a", 1.0, 0.3], ["b", 0.3, 1.0]],
    }
    assert (
        build_figure(ChartConfig(type="heatmap", table="matrix"), [matrix])["figure"]["data"][0][
            "type"
        ]
        == "heatmap"
    )
    fc = {
        "name": "forecast",
        "columns": ["period", "value", "kind", "lower", "upper"],
        "rows": [["2025-01-01", 1, "actual", None, None], ["2025-02-01", 2, "forecast", 1.5, 2.5]],
    }
    fig = build_figure(ChartConfig(type="forecast", table="forecast"), [fc])["figure"]
    assert [t["name"] for t in fig["data"]] == ["actual", "approx. band", "forecast"]


def test_unknown_column_rejected() -> None:
    with pytest.raises(ChartError):
        build_figure(ChartConfig(type="bar", x="nope", y="value"), [TABLE])


def test_config_rejects_unknown_fields_and_types() -> None:
    with pytest.raises(ValueError):
        ChartConfig.model_validate({"type": "pie", "x": "a", "y": "b"})
    with pytest.raises(ValueError):
        ChartConfig.model_validate({"type": "bar", "onclick": "alert(1)"})


def test_validate_spec_rejects_foreign_trace_and_properties() -> None:
    with pytest.raises(ChartError):
        validate_spec({"data": [{"type": "scattermapbox"}], "layout": {}})
    with pytest.raises(ValueError):
        validate_spec({"data": [{"type": "bar", "evil": "<script>"}], "layout": {}})


def test_suggest_config_uses_horizontal_bars_for_many_categories() -> None:
    rows = [[f"c{i}", "x", i] for i in range(20)]
    cfg = suggest_config({"type": "bar", "x": "region", "y": "value"}, [{**TABLE, "rows": rows}])
    assert cfg is not None and cfg.orientation == "h"


CSV = b"region,revenue,discount\n" + b"".join(
    f"{r},{10 + i},{i / 100}\n".encode() for i, r in enumerate(["East", "West", "North"] * 20)
)


def test_agent_attaches_charts_and_chart_studio_rerenders(client: TestClient) -> None:
    client.post("/api/datasets", files={"file": ("orders.csv", CSV)})
    a = client.post("/api/analyses", json={"question": "total revenue by region"}).json()
    assert a["charts"] and a["charts"][0]["figure"]["data"][0]["type"] == "bar"
    body: dict[str, Any] = {"step": 1, "config": {"type": "treemap", "x": "region", "y": "value"}}
    res = client.post(f"/api/analyses/{a['id']}/charts/preview", json=body)
    assert res.status_code == 200 and res.json()["figure"]["data"][0]["type"] == "treemap"
    saved = client.put(f"/api/analyses/{a['id']}/charts", json=[body]).json()
    assert saved["charts"][0]["config"]["type"] == "treemap"
    bad = client.post(
        f"/api/analyses/{a['id']}/charts/preview",
        json={"step": 1, "config": {"type": "bar", "x": "secret", "y": "value"}},
    )
    assert bad.status_code == 422


def test_box_chart_uses_sandboxed_sample(client: TestClient) -> None:
    client.post("/api/datasets", files={"file": ("orders.csv", CSV)})
    a = client.post(
        "/api/analyses", json={"question": "compare revenue between region groups"}
    ).json()
    assert a["steps"][0]["op"] == "group_compare"
    raw = next(t for t in a["steps"][0]["tables"] if t["name"] == "raw")
    assert len(raw["rows"]) == 60 and raw["columns"] == ["region", "revenue"]
    assert {t["type"] for t in a["charts"][0]["figure"]["data"]} == {"box"}
