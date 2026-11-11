"""Server-side Plotly figure construction.

Figures are built only from computed result tables (or sandboxed queries for raw-data
charts like box plots), validated by Plotly's own property schema
(``plotly.graph_objects.Figure`` raises on unknown attributes), and serialised to JSON.
No model output is ever passed through as figure JSON, and no JavaScript is involved.
"""

from __future__ import annotations

import json
from typing import Any, Literal

import plotly.graph_objects as go
from pydantic import BaseModel, ConfigDict, Field

ChartType = Literal[
    "line", "area", "bar", "stacked_bar", "grouped_bar", "scatter", "histogram", "box",
    "heatmap", "treemap", "funnel", "forecast",
]  # fmt: skip
ALLOWED_TRACES = {"scatter", "bar", "histogram", "box", "heatmap", "treemap", "funnel"}
MAX_CATEGORIES = 30


class ChartConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: ChartType
    table: str = "result"
    x: str | None = None
    y: str | None = None
    color: str | None = None
    title: str | None = Field(default=None, max_length=200)
    orientation: Literal["v", "h"] = "v"
    top_n: int = Field(default=MAX_CATEGORIES, ge=1, le=200)
    category_filter: list[str] = Field(default_factory=list, max_length=200)
    log_y: bool = False
    value_suffix: str | None = Field(default=None, max_length=4)


class ChartError(ValueError):
    pass


def _col(table: dict[str, Any], name: str | None) -> int:
    if name is None or name not in table["columns"]:
        raise ChartError(f"Column '{name}' is not in result table '{table['name']}'")
    return int(table["columns"].index(name))


def _filtered_rows(table: dict[str, Any], cfg: ChartConfig, key: int | None) -> list[list[Any]]:
    rows: list[list[Any]] = table["rows"]
    if cfg.category_filter and key is not None:
        keep = set(cfg.category_filter)
        rows = [r for r in rows if str(r[key]) in keep]
    return rows


def build_figure(cfg: ChartConfig, tables: list[dict[str, Any]]) -> dict[str, Any]:
    table = next((t for t in tables if t["name"] == cfg.table), None)
    if table is None:
        raise ChartError(f"No result table named '{cfg.table}'")
    fig = go.Figure()
    t = cfg.type
    if t in {"line", "area", "bar", "stacked_bar", "grouped_bar", "funnel"}:
        xi, yi = _col(table, cfg.x), _col(table, cfg.y)
        ci = _col(table, cfg.color) if cfg.color else None
        rows = _filtered_rows(table, cfg, ci if ci is not None else xi)
        series: dict[Any, list[list[Any]]] = {}
        for r in rows:
            series.setdefault(r[ci] if ci is not None else None, []).append(r)
        if ci is None and t in {"bar", "funnel"} and len(rows) > cfg.top_n:
            rows = sorted(rows, key=lambda r: -(r[yi] or 0))[: cfg.top_n]
            series = {None: rows}
        for name, rs in list(series.items())[: cfg.top_n]:
            xs, ys = [r[xi] for r in rs], [r[yi] for r in rs]
            label = None if name is None else str(name)
            if t == "funnel":
                fig.add_trace(go.Funnel(x=ys, y=xs, name=label))
            elif t in {"line", "area"}:
                fig.add_trace(
                    go.Scatter(
                        x=xs,
                        y=ys,
                        name=label,
                        mode="lines+markers",
                        fill="tozeroy"
                        if t == "area" and ci is None
                        else ("tonexty" if t == "area" else None),
                        stackgroup="one" if t == "area" and ci is not None else None,
                    )
                )
            else:
                h = cfg.orientation == "h"
                fig.add_trace(
                    go.Bar(
                        x=ys if h else xs,
                        y=xs if h else ys,
                        name=label,
                        orientation=cfg.orientation,
                    )
                )
        if t == "stacked_bar":
            fig.update_layout(barmode="stack")
        elif t == "grouped_bar":
            fig.update_layout(barmode="group")
        _axes(fig, cfg, cfg.x, cfg.y)
    elif t == "forecast":
        xi, yi = _col(table, cfg.x or "period"), _col(table, cfg.y or "value")
        ki, lo, hi = _col(table, "kind"), _col(table, "lower"), _col(table, "upper")
        act = [r for r in table["rows"] if r[ki] == "actual"]
        fc = [r for r in table["rows"] if r[ki] == "forecast"]
        fig.add_trace(
            go.Scatter(
                x=[r[xi] for r in act], y=[r[yi] for r in act], name="actual", mode="lines+markers"
            )
        )
        if fc:
            fig.add_trace(
                go.Scatter(
                    x=[r[xi] for r in fc] + [r[xi] for r in reversed(fc)],
                    y=[r[hi] for r in fc] + [r[lo] for r in reversed(fc)],
                    fill="toself",
                    name="approx. band",
                    line={"width": 0},
                    hoverinfo="skip",
                    opacity=0.25,
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[act[-1][xi], *[r[xi] for r in fc]],
                    y=[act[-1][yi], *[r[yi] for r in fc]],
                    name="forecast",
                    mode="lines+markers",
                    line={"dash": "dash"},
                )
            )
        _axes(fig, cfg, "period", cfg.y or "value")
    elif t == "heatmap":
        cols = table["columns"]
        z = [[(v if isinstance(v, (int, float)) else None) for v in r[1:]] for r in table["rows"]]
        if table["name"] == "retention":  # cohort matrix: skip size column
            z = [[v for v in r[2:]] for r in table["rows"]]
            cols = [cols[0], *cols[2:]]
        fig.add_trace(
            go.Heatmap(
                z=z,
                x=cols[1:],
                y=[str(r[0]) for r in table["rows"]],
                colorscale="Viridis",
                hoverongaps=False,
                zmid=0 if table["name"] == "matrix" else None,
            )
        )
        fig.update_layout(yaxis={"autorange": "reversed"})
    elif t == "treemap":
        xi, yi = _col(table, cfg.x), _col(table, cfg.y)
        rows = [r for r in table["rows"] if isinstance(r[yi], (int, float)) and r[yi] > 0]
        fig.add_trace(
            go.Treemap(
                labels=[str(r[xi]) for r in rows],
                parents=[""] * len(rows),
                values=[r[yi] for r in rows],
            )
        )
    elif t in {"scatter", "histogram", "box"}:
        # raw-data charts receive a "raw" table assembled by the caller from a sandboxed query
        rx: int | None = _col(table, cfg.x) if cfg.x else None
        ry: int | None = _col(table, cfg.y) if cfg.y else None
        if t == "scatter":
            if rx is None or ry is None:
                raise ChartError("scatter needs x and y")
            fig.add_trace(
                go.Scattergl(
                    x=[r[rx] for r in table["rows"]],
                    y=[r[ry] for r in table["rows"]],
                    mode="markers",
                    marker={"size": 5, "opacity": 0.6},
                    name=cfg.y,
                )
            )
        elif t == "histogram":
            col = rx if rx is not None else ry
            if col is None:
                raise ChartError("histogram needs x")
            fig.add_trace(go.Histogram(x=[r[col] for r in table["rows"]], nbinsx=40))
        else:
            if ry is None:
                raise ChartError("box needs y")
            groups: dict[Any, list[Any]] = {}
            for r in table["rows"]:
                groups.setdefault(r[rx] if rx is not None else "all", []).append(r[ry])
            for name, vals in list(groups.items())[: cfg.top_n]:
                fig.add_trace(go.Box(y=vals, name=str(name), boxpoints="outliers"))
        _axes(fig, cfg, cfg.x, cfg.y)
    else:  # pragma: no cover - Literal exhausts types
        raise ChartError(f"Unsupported chart type {t}")
    if cfg.log_y:
        fig.update_yaxes(type="log")
    fig.update_layout(
        title={"text": cfg.title} if cfg.title else None,
        hovermode="closest" if t in {"scatter", "box"} else "x unified",
        legend={"orientation": "h", "y": -0.28, "x": 0},
        margin={"l": 48, "r": 16, "t": 48 if cfg.title else 16, "b": 48},
    )
    spec = json.loads(fig.to_json())
    spec["layout"].pop("template", None)  # theming is applied by the frontend
    validate_spec(spec)
    return {"config": cfg.model_dump(), "figure": spec}


def _axes(fig: go.Figure, cfg: ChartConfig, x: str | None, y: str | None) -> None:
    h = cfg.orientation == "h" and cfg.type in {"bar", "stacked_bar", "grouped_bar"}
    fig.update_xaxes(title_text=(y if h else x) or "")
    fig.update_yaxes(title_text=(x if h else y) or "", ticksuffix=cfg.value_suffix or "")


def validate_spec(spec: dict[str, Any]) -> None:
    """Defence in depth: only known trace types, and the figure must round-trip Plotly's
    validator (unknown properties raise)."""
    for trace in spec.get("data", []):
        base = trace.get("type", "scatter").removesuffix("gl")
        if base not in ALLOWED_TRACES:
            raise ChartError(f"Trace type {trace.get('type')} is not allowed")
    go.Figure(spec)


def suggest_config(
    hint: dict[str, Any] | None, tables: list[dict[str, Any]], title: str | None = None
) -> ChartConfig | None:
    """Pick a sensible chart from an operation's hint and the actual result shape."""
    if not hint or not tables:
        return None
    t = hint.get("type")
    name = hint.get("table", tables[0]["name"])
    table = next((x for x in tables if x["name"] == name), tables[0])
    if not table["rows"]:
        return None
    if t == "bar" and hint.get("x") and len(table["rows"]) > 12:
        return ChartConfig(
            type="bar",
            table=table["name"],
            x=hint["x"],
            y=hint["y"],
            orientation="h",
            title=title,
            top_n=MAX_CATEGORIES,
        )
    if t in {"bar", "line", "stacked_bar"}:
        return ChartConfig(
            type=t,
            table=table["name"],
            x=hint["x"],
            y=hint["y"],
            color=hint.get("color"),
            title=title,
        )
    if t in {"heatmap", "forecast"}:
        return ChartConfig(
            type=t, table=table["name"], title=title, value_suffix=hint.get("value_suffix")
        )
    if t in {"box", "scatter"}:
        return ChartConfig(type=t, table="raw", x=hint.get("x"), y=hint.get("y"), title=title)
    return None
