"""Deterministic *fixture* provider for tests and offline demos.

This is NOT a language model. It is a keyword heuristic that emits plans and explanation
drafts in the same JSON contract as a real model, so the agent graph, validators and
verifier can be tested reproducibly in CI. Results produced with it are labelled
``provider: fixture`` everywhere.
"""

from __future__ import annotations

import re
from typing import Any

from insightforge.llm.base import LLMUsage, Task


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _match_cols(question: str, cols: list[dict[str, Any]]) -> list[dict[str, Any]]:
    q = question.lower()
    words = _words(question)
    hits = []
    for c in cols:
        name = c["name"].lower()
        parts = set(re.findall(r"[a-z0-9]+", name))
        stems = {p.rstrip("s") for p in parts}
        if name in q or parts <= words or stems & {w.rstrip("s") for w in words}:
            hits.append(c)
    return hits


class FixtureProvider:
    name = "fixture"
    model = "fixture-heuristic-v1"

    def __init__(self) -> None:
        self.usage = LLMUsage()

    def complete_json(
        self, *, task: Task, system: str, user: str, schema: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.usage.calls += 1
        if task == "plan":
            return self._plan(payload["question"], payload["catalog"])
        return self._explain(payload)

    def _plan(self, question: str, catalog: list[dict[str, Any]]) -> dict[str, Any]:
        if not catalog:
            return {
                "needs_clarification": True,
                "clarification_question": "Upload a dataset first.",
                "assumptions": [],
                "steps": [],
            }
        scored = sorted(catalog, key=lambda t: -len(_match_cols(question, t["columns"])))
        t = scored[0]
        hits = _match_cols(question, t["columns"])
        w = _words(question)
        num = [c for c in hits if c["kind"] == "numeric" and c.get("role") != "identifier"]
        binary = [c for c in hits if c.get("role") == "binary_flag"]
        dims = [c for c in hits if c["name"] in t["dimensions"] and c not in binary]
        dates = t["date_columns"]
        base = {"dataset": t["table"]}

        def step(args: dict[str, Any], purpose: str) -> dict[str, Any]:
            return {
                "needs_clarification": False,
                "clarification_question": None,
                "assumptions": [],
                "steps": [{"tool": "op", "purpose": purpose, "args": {**base, **args}}],
            }

        if w & {"missing", "null", "nulls"}:
            return step({"op": "missing_values"}, "Investigate missing values")
        if w & {"forecast", "predict", "projection"} and num and dates:
            return step(
                {
                    "op": "forecast",
                    "measure": num[0]["name"],
                    "date_column": dates[0],
                    "grain": "month",
                    "horizon": 6,
                },
                "Forecast",
            )
        if w & {"cohort", "retention", "retain"} and dates:
            ent = next(
                (
                    c["name"]
                    for c in t["columns"]
                    if c.get("role") == "identifier" or c["name"].endswith("_id")
                ),
                None,
            )
            if ent:
                return step(
                    {
                        "op": "cohort_retention",
                        "entity_column": ent,
                        "date_column": dates[0],
                        "grain": "month",
                        "max_periods": 6,
                    },
                    "Cohort retention",
                )
        if w & {"correlation", "relationship", "correlate", "related"} and len(num) >= 2:
            return step(
                {"op": "correlation", "columns": [c["name"] for c in num[:4]]}, "Correlation"
            )
        if w & {"segment", "segments", "cluster", "clusters"} and num and not dims:
            return step(
                {"op": "segment", "features": [c["name"] for c in num[:4]], "k": 4}, "Segmentation"
            )
        if binary:
            return step(
                {
                    "op": "rate",
                    "outcome": binary[0]["name"],
                    "group_by": [d["name"] for d in dims[:1]],
                },
                "Rate by group",
            )
        if w & {"outlier", "outliers", "abnormal", "unusual", "anomalies"} and num:
            return step(
                {
                    "op": "outliers",
                    "column": num[0]["name"],
                    "group_by": dims[0]["name"] if dims else None,
                },
                "Outliers",
            )
        if w & {"compare", "difference", "versus", "vs"} and num and dims:
            return step(
                {"op": "group_compare", "measure": num[0]["name"], "group_column": dims[0]["name"]},
                "Group comparison",
            )
        if w & {"trend", "growth", "monthly", "over", "time", "grew"} and dates:
            return step(
                {
                    "op": "trend",
                    "measure": num[0]["name"] if num else None,
                    "agg": "sum" if num else "count",
                    "date_column": dates[0],
                    "grain": "quarter" if "quarter" in w else "month",
                    "group_by": dims[0]["name"] if dims else None,
                },
                "Trend",
            )
        if num or dims or w & {"how", "many", "count", "number"}:
            agg = "avg" if w & {"average", "mean", "avg"} else ("sum" if num else "count")
            return step(
                {
                    "op": "aggregate",
                    "measure": num[0]["name"] if num else None,
                    "agg": agg,
                    "group_by": [d["name"] for d in dims[:2]],
                },
                "Aggregate",
            )
        return {
            "needs_clarification": True,
            "clarification_question": (
                f"Which measure in '{t['table']}' should I analyse? Available: "
                + ", ".join(t["measures"][:8])
            ),
            "assumptions": [],
            "steps": [],
        }

    def _explain(self, payload: dict[str, Any]) -> dict[str, Any]:
        facts = payload.get("facts", [])
        cited = [f for f in facts if f["unit"] != "pvalue"][:4]
        sentences = [f"The {f['label']} is {{{{{f['id']}}}}}." for f in cited]
        pv = next((f for f in facts if f["unit"] == "pvalue"), None)
        if pv:
            sentences.append(f"The {pv['label']} is {{{{{pv['id']}}}}}.")
        return {
            "headline": cited[0]["label"].capitalize() if cited else "Analysis complete",
            "explanation": " ".join(sentences) or "No numeric results were produced.",
        }
