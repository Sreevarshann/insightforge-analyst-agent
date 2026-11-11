"""LLM provider abstraction.

Providers return *proposals* (JSON plans, explanation drafts). Nothing a provider returns
is trusted: plans are schema-validated and executed only through typed operations or the
SQL policy + sandbox, and explanations are verified against computed facts.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Task = Literal["plan", "explain"]


class LLMError(RuntimeError):
    pass


@dataclass
class LLMUsage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    log: list[dict[str, Any]] = field(default_factory=list)


class LLMProvider(Protocol):
    name: str
    model: str
    usage: LLMUsage

    def complete_json(
        self,
        *,
        task: Task,
        system: str,
        user: str,
        schema: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a JSON object for ``task``. ``payload`` carries the same information as
        the prompt in structured form (used by the deterministic fixture provider)."""
        ...


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = _FENCE.sub("", _THINK.sub("", text)).strip()
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise LLMError("Model did not return JSON") from None
        try:
            obj = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError("Model returned malformed JSON") from exc
    if not isinstance(obj, dict):
        raise LLMError("Model JSON was not an object")
    return obj
