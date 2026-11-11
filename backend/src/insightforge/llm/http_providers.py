"""Ollama (local) and OpenAI-compatible chat providers with JSON-schema constrained output."""

from __future__ import annotations

import time
from typing import Any

import httpx

from insightforge.llm.base import LLMError, LLMUsage, Task, parse_json_object


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float = 120.0) -> None:
        self.model = model
        self.usage = LLMUsage()
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def complete_json(
        self, *, task: Task, system: str, user: str, schema: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        body = {
            "model": self.model,
            "stream": False,
            "format": schema,  # Ollama structured outputs: decoding constrained to the schema
            "options": {"temperature": 0, "seed": 7, "num_ctx": 8192},
            "think": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        started = time.perf_counter()
        try:
            res = self._client.post("/api/chat", json=body)
            res.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError(f"Ollama request failed: {type(exc).__name__}") from exc
        data = res.json()
        elapsed = (time.perf_counter() - started) * 1000
        self.usage.calls += 1
        self.usage.prompt_tokens += int(data.get("prompt_eval_count", 0))
        self.usage.completion_tokens += int(data.get("eval_count", 0))
        self.usage.latency_ms += elapsed
        self.usage.log.append({"task": task, "latency_ms": round(elapsed, 1)})
        return parse_json_object(data.get("message", {}).get("content", ""))


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, base_url: str, model: str, api_key: str | None, timeout: float = 120.0):
        self.model = model
        self.usage = LLMUsage()
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout, headers=headers)

    def complete_json(
        self, *, task: Task, system: str, user: str, schema: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": task, "schema": schema},
            },
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        started = time.perf_counter()
        try:
            res = self._client.post("/v1/chat/completions", json=body)
            res.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM request failed: {type(exc).__name__}") from exc
        data = res.json()
        elapsed = (time.perf_counter() - started) * 1000
        usage = data.get("usage") or {}
        self.usage.calls += 1
        self.usage.prompt_tokens += int(usage.get("prompt_tokens", 0))
        self.usage.completion_tokens += int(usage.get("completion_tokens", 0))
        self.usage.latency_ms += elapsed
        self.usage.log.append({"task": task, "latency_ms": round(elapsed, 1)})
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMError("LLM response had no content") from exc
        return parse_json_object(content)
