"""Run the analysis graph, stream its events and persist a reproducible record."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from insightforge.agent.graph import AgentState, build_graph
from insightforge.config import Settings
from insightforge.db.models import Analysis
from insightforge.llm.base import LLMProvider

EventSink = Callable[[dict[str, Any]], None]
ExplainFactory = Callable[[LLMProvider], Callable[[AgentState], AgentState]]


def deterministic_summary(_: LLMProvider) -> Callable[[AgentState], AgentState]:
    """Fallback explainer: restates the first computed facts verbatim (no LLM involved)."""

    def node(state: AgentState) -> AgentState:
        facts = [f for r in state.get("results", []) for f in r["facts"]][:5]
        text = " ".join(f"{f['label']}: {f['value']}." for f in facts)
        return {
            "explanation": {
                "headline": "Computed results",
                "text": text,
                "verification": {"status": "deterministic"},
            }
        }

    return node


def run_analysis(
    db: Session,
    settings: Settings,
    provider: LLMProvider,
    question: str,
    *,
    dataset_ids: list[str] | None = None,
    on_event: EventSink | None = None,
    explain_factory: ExplainFactory = deterministic_summary,
) -> Analysis:
    started = time.perf_counter()
    analysis = Analysis(
        question=question, status="running", model_name=f"{provider.name}:{provider.model}"
    )
    db.add(analysis)
    db.commit()
    emit = on_event or (lambda _e: None)
    emit({"type": "analysis", "id": analysis.id, "status": "running"})
    graph = build_graph(db, settings, provider, explain_factory(provider))
    state: dict[str, Any] = {}
    init: AgentState = {
        "analysis_id": analysis.id,
        "question": question,
        "dataset_ids": dataset_ids or [],
    }
    try:
        for mode, chunk in graph.stream(init, stream_mode=["custom", "values"]):
            if mode == "custom":
                emit(chunk)
            else:
                state = chunk
    except Exception:
        analysis.status = "failed"
        analysis.duration_ms = int((time.perf_counter() - started) * 1000)
        db.commit()
        emit({"type": "analysis", "id": analysis.id, "status": "failed"})
        raise
    results = state.get("results", [])
    analysis.plan_json = {
        "raw": state.get("plan"),
        "steps": state.get("validated_steps", []),
        "attempts": state.get("attempts", 0),
        "errors": state.get("errors", []),
        "trace": state.get("trace", []),
        "llm_usage": {
            "calls": provider.usage.calls,
            "prompt_tokens": provider.usage.prompt_tokens,
            "completion_tokens": provider.usage.completion_tokens,
            "latency_ms": round(provider.usage.latency_ms, 1),
        },
    }
    analysis.steps_json = results
    analysis.dataset_versions = sorted({v for r in results for v in r.get("dataset_versions", [])})
    explanation = state.get("explanation") or {}
    analysis.charts_json = state.get("charts", [])
    if state.get("clarification"):
        analysis.status = "needs_clarification"
        analysis.explanation = state["clarification"]
    elif results:
        analysis.status = "completed"
        analysis.title = explanation.get("headline")
        analysis.explanation = explanation.get("text")
        analysis.verification_json = explanation.get("verification")
    else:
        analysis.status = "failed"
        analysis.explanation = "The analysis could not be completed: " + "; ".join(
            state.get("errors", []) or ["no executable plan"]
        )
    analysis.duration_ms = int((time.perf_counter() - started) * 1000)
    db.commit()
    emit({"type": "analysis", "id": analysis.id, "status": analysis.status})
    return analysis
