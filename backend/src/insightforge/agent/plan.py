"""The plan contract between the LLM planner and the executor."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

from insightforge.ops.models import OpArgs

op_adapter: TypeAdapter[Any] = TypeAdapter(OpArgs)


class PlanStep(BaseModel):
    tool: Literal["op", "sql"]
    purpose: str = Field(default="", max_length=300)
    args: dict[str, Any] | None = None
    sql: str | None = Field(default=None, max_length=20_000)


class Plan(BaseModel):
    needs_clarification: bool = False
    clarification_question: str | None = None
    assumptions: list[str] = Field(default_factory=list, max_length=10)
    steps: list[PlanStep] = Field(default_factory=list, max_length=4)


# JSON schema handed to the model's constrained decoder. Kept deliberately small so that
# small local models can follow it; detailed op argument rules live in the prompt and are
# enforced afterwards by Pydantic.
PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "needs_clarification": {"type": "boolean"},
        "clarification_question": {"type": ["string", "null"]},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "steps": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "tool": {"type": "string", "enum": ["op", "sql"]},
                    "purpose": {"type": "string"},
                    "args": {"type": ["object", "null"]},
                    "sql": {"type": ["string", "null"]},
                },
                "required": ["tool", "purpose"],
            },
        },
    },
    "required": ["needs_clarification", "assumptions", "steps"],
}
