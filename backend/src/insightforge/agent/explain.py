"""Explanation node: LLM drafts with fact placeholders, the verifier checks and renders."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from insightforge.agent.graph import AgentState, _emit, _trace
from insightforge.agent.prompts import EXPLAIN_SYSTEM, EXPLAIN_USER
from insightforge.llm.base import LLMError, LLMProvider
from insightforge.verify.numbers import NUMBER, PLACEHOLDER, format_value, verify_explanation

MAX_FACTS_IN_PROMPT = 40
EXPLAIN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"headline": {"type": "string"}, "explanation": {"type": "string"}},
    "required": ["headline", "explanation"],
}


def _fallback(facts: list[dict[str, Any]]) -> str:
    picked = [f for f in facts if f["unit"] != "pvalue"][:4]
    return " ".join(
        f"{f['label'][:1].upper()}{f['label'][1:]}: {format_value(f['value'], f['unit'])}."
        for f in picked
    )


def llm_explainer(provider: LLMProvider) -> Callable[[AgentState], AgentState]:
    def node(state: AgentState) -> AgentState:
        t0 = time.perf_counter()
        _emit({"type": "stage", "stage": "explain", "status": "start"})
        results = state.get("results", [])
        if not results:
            return {
                "explanation": {"headline": None, "text": None, "verification": None},
                "trace": _trace(state, "explain", t0, skipped=True),
            }
        facts = [f for r in results for f in r["facts"]]
        notes = [n for r in results for n in r.get("notes", [])]
        assumptions = (state.get("plan") or {}).get("assumptions", [])
        shown = facts[:MAX_FACTS_IN_PROMPT]
        user = EXPLAIN_USER.format(
            question=state["question"],
            assumptions="; ".join(assumptions) or "none",
            notes="; ".join(notes) or "none",
            facts="\n".join(
                f"{f['id']} | {f['label']} | {format_value(f['value'], f['unit'])}" for f in shown
            ),
        )
        headline, draft, error = None, "", None
        try:
            out = provider.complete_json(
                task="explain",
                system=EXPLAIN_SYSTEM,
                user=user,
                schema=EXPLAIN_SCHEMA,
                payload={"question": state["question"], "facts": shown, "notes": notes},
            )
            headline, draft = str(out.get("headline", ""))[:120], str(out.get("explanation", ""))
        except LLMError as exc:
            error = str(exc)
        v = verify_explanation(draft, facts, question=state["question"])
        verification = v.as_dict()
        verification["draft"] = draft
        text = v.text
        if v.status == "abstained" or not text:
            text = _fallback(facts)
            verification["status"] = "abstained"
            verification["fallback"] = "deterministic summary of computed facts"
            if error:
                verification["llm_error"] = error
        if headline and (
            NUMBER.search(PLACEHOLDER.sub("", headline)) or PLACEHOLDER.search(headline)
        ):
            headline = None  # headlines must be number-free
        explanation = {
            "headline": headline or (results[0].get("purpose") or "Analysis result"),
            "text": text,
            "verification": verification,
            "assumptions": assumptions,
            "notes": notes,
        }
        _emit({"type": "explanation", "explanation": explanation})
        return {
            "explanation": explanation,
            "trace": _trace(state, "explain", t0, verification=verification["status"]),
        }

    return node
