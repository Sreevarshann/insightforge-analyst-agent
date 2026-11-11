"""LangGraph analysis state machine.

    catalog -> plan -> validate --(invalid, retries left)--> plan
                        |                                     ^
                        v                                     |
                     execute -> inspect --(failed, retries)---+
                        |            |
                  (clarify)          v
                        |         explain -> END
                        v
                       END

The LLM only appears in ``plan`` and ``explain``. Everything it proposes is validated,
executed through typed operations / the SQL sandbox, and (in ``explain``) checked against
computed facts before it reaches the user.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from typing import Any, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError
from sqlalchemy.orm import Session

from insightforge.agent.catalog import build_catalog, catalog_text
from insightforge.agent.plan import PLAN_JSON_SCHEMA, Plan, op_adapter
from insightforge.agent.prompts import PLAN_FEEDBACK, PLANNER_SYSTEM, PLANNER_USER
from insightforge.agent.sqlfacts import sql_to_result
from insightforge.charts.builder import ChartError, build_figure, suggest_config
from insightforge.config import Settings
from insightforge.llm.base import LLMError, LLMProvider
from insightforge.ops.context import OpContext, OpError
from insightforge.ops.operations import run_operation
from insightforge.sql.service import QueryFailed, execute_query
from insightforge.sql.validator import SQLRejected, validate_sql

MAX_PLAN_ATTEMPTS = 3


class AgentState(TypedDict, total=False):
    analysis_id: str
    question: str
    dataset_ids: list[str]
    catalog: list[dict[str, Any]]
    plan: dict[str, Any]
    validated_steps: list[dict[str, Any]]
    results: list[dict[str, Any]]
    errors: list[str]
    attempts: int
    clarification: str | None
    explanation: dict[str, Any]
    charts: list[dict[str, Any]]
    trace: list[dict[str, Any]]


def _emit(event: dict[str, Any]) -> None:
    with contextlib.suppress(RuntimeError):  # not running under a streaming invocation
        get_stream_writer()(event)


def _trace(state: AgentState, node: str, started: float, **detail: Any) -> list[dict[str, Any]]:
    entry = {"node": node, "ms": round((time.perf_counter() - started) * 1000, 1), **detail}
    _emit({"type": "stage", "stage": node, "status": "done", **entry})
    return [*state.get("trace", []), entry]


def build_graph(
    db: Session,
    settings: Settings,
    provider: LLMProvider,
    explain_node: Callable[[AgentState], AgentState],
) -> Any:
    def catalog(state: AgentState) -> AgentState:
        t0 = time.perf_counter()
        _emit({"type": "stage", "stage": "catalog", "status": "start"})
        cat = build_catalog(db, state.get("dataset_ids") or None)
        return {
            "catalog": cat,
            "attempts": 0,
            "errors": [],
            "trace": _trace(state, "catalog", t0, tables=[c["table"] for c in cat]),
        }

    def plan(state: AgentState) -> AgentState:
        t0 = time.perf_counter()
        _emit(
            {
                "type": "stage",
                "stage": "plan",
                "status": "start",
                "attempt": state.get("attempts", 0) + 1,
            }
        )
        errors = state.get("errors", [])
        feedback = (
            PLAN_FEEDBACK.format(errors="\n".join(f"- {e}" for e in errors)) if errors else ""
        )
        user = PLANNER_USER.format(
            question=state["question"], catalog=catalog_text(state["catalog"]), feedback=feedback
        )
        try:
            raw = provider.complete_json(
                task="plan",
                system=PLANNER_SYSTEM,
                user=user,
                schema=PLAN_JSON_SCHEMA,
                payload={
                    "question": state["question"],
                    "catalog": state["catalog"],
                    "errors": errors,
                },
            )
        except LLMError as exc:
            raw = {"needs_clarification": False, "assumptions": [], "steps": [], "_error": str(exc)}
        _emit({"type": "plan", "plan": raw})
        return {
            "plan": raw,
            "attempts": state.get("attempts", 0) + 1,
            "trace": _trace(state, "plan", t0, attempt=state.get("attempts", 0) + 1),
        }

    def validate(state: AgentState) -> AgentState:
        t0 = time.perf_counter()
        raw = state["plan"]
        errors: list[str] = []
        if "_error" in raw:
            errors.append(f"Planner error: {raw['_error']}")
        try:
            p = Plan.model_validate({k: v for k, v in raw.items() if not k.startswith("_")})
        except ValidationError as exc:
            p, errors = Plan(), [*errors, f"Plan structure invalid: {exc.errors()[0]['msg']}"]
        if p.needs_clarification:
            q = p.clarification_question or "Could you clarify the question?"
            return {
                "clarification": q,
                "validated_steps": [],
                "errors": [],
                "trace": _trace(state, "validate", t0, clarification=True),
            }
        tables = [c["table"] for c in state["catalog"]]
        steps: list[dict[str, Any]] = []
        for i, s in enumerate(p.steps):
            try:
                if s.tool == "op":
                    args = op_adapter.validate_python(s.args or {})
                    if args.dataset not in tables:
                        raise OpError(f"Unknown dataset '{args.dataset}'")
                    steps.append(
                        {"tool": "op", "purpose": s.purpose, "args": args.model_dump(mode="json")}
                    )
                else:
                    validate_sql(s.sql or "", tables)
                    steps.append({"tool": "sql", "purpose": s.purpose, "sql": s.sql})
            except ValidationError as exc:
                e = exc.errors()[0]
                errors.append(f"Step {i + 1}: {'.'.join(str(x) for x in e['loc'])}: {e['msg']}")
            except (OpError, SQLRejected) as exc:
                errors.append(f"Step {i + 1}: {exc}")
        if not steps and not errors:
            errors.append("The plan contained no executable steps.")
        return {
            "validated_steps": steps if not errors else [],
            "errors": errors,
            "clarification": None,
            "trace": _trace(state, "validate", t0, valid_steps=len(steps), errors=errors),
        }

    def execute(state: AgentState) -> AgentState:
        t0 = time.perf_counter()
        _emit({"type": "stage", "stage": "execute", "status": "start"})
        results, errors = [], []
        for i, s in enumerate(state["validated_steps"]):
            ctx = OpContext(db=db, settings=settings, analysis_id=state.get("analysis_id"))
            try:
                if s["tool"] == "op":
                    r = run_operation(ctx, op_adapter.validate_python(s["args"]))
                else:
                    q = execute_query(
                        db, settings, s["sql"], origin="agent", analysis_id=state.get("analysis_id")
                    )
                    r = sql_to_result(q, s["purpose"])
                result = {"step": i + 1, "purpose": s["purpose"], **r.model_dump(mode="json")}
                results.append(result)
                _emit({"type": "result", "result": result})
            except (OpError, SQLRejected, QueryFailed) as exc:
                errors.append(f"Step {i + 1} ({s.get('args', {}).get('op', s['tool'])}): {exc}")
        return {
            "results": results,
            "errors": errors,
            "trace": _trace(state, "execute", t0, steps=len(results), errors=errors),
        }

    def inspect(state: AgentState) -> AgentState:
        t0 = time.perf_counter()
        notes = []
        for r in state.get("results", []):
            if all(not t["rows"] for t in r["tables"]):
                notes.append(f"Step {r['step']} returned no rows; filters may exclude all data.")
        return {"trace": _trace(state, "inspect", t0, notes=notes)}

    def charts(state: AgentState) -> AgentState:
        t0 = time.perf_counter()
        _emit({"type": "stage", "stage": "charts", "status": "start"})
        out, notes = [], []
        for r in state.get("results", []):
            hint = r.get("chart_hint")
            cfg = suggest_config(hint, r["tables"], title=r.get("purpose") or None)
            if cfg is None:
                continue
            try:
                fig = build_figure(cfg, r["tables"])
                chart = {"step": r["step"], **fig}
                out.append(chart)
                _emit({"type": "chart", "chart": chart})
            except ChartError as exc:
                notes.append(f"Step {r['step']}: {exc}")
        return {
            "charts": out,
            "trace": _trace(state, "charts", t0, charts=len(out), notes=notes),
        }

    def after_validate(state: AgentState) -> str:
        if state.get("clarification"):
            return "end"
        if state.get("errors"):
            return "plan" if state.get("attempts", 0) < MAX_PLAN_ATTEMPTS else "explain"
        return "execute"

    def after_inspect(state: AgentState) -> str:
        if (
            state.get("errors")
            and not state.get("results")
            and state.get("attempts", 0) < MAX_PLAN_ATTEMPTS
        ):
            return "plan"
        return "explain"

    def explain(state: AgentState) -> AgentState:
        return explain_node(state)

    g = StateGraph(AgentState)
    g.add_node("catalog", catalog)
    g.add_node("plan", plan)
    g.add_node("validate", validate)
    g.add_node("execute", execute)
    g.add_node("inspect", inspect)
    g.add_node("charts", charts)
    g.add_node("explain", explain)
    g.add_edge(START, "catalog")
    g.add_edge("catalog", "plan")
    g.add_edge("plan", "validate")
    g.add_conditional_edges(
        "validate",
        after_validate,
        {"plan": "plan", "execute": "execute", "explain": "explain", "end": END},
    )
    g.add_edge("execute", "inspect")
    g.add_conditional_edges("inspect", after_inspect, {"plan": "plan", "explain": "charts"})
    g.add_edge("charts", "explain")
    g.add_edge("explain", END)
    return g.compile()
