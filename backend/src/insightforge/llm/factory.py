from __future__ import annotations

from insightforge.config import Settings
from insightforge.llm.base import LLMProvider
from insightforge.llm.fixture import FixtureProvider
from insightforge.llm.http_providers import OllamaProvider, OpenAICompatibleProvider


def make_provider(settings: Settings) -> LLMProvider:
    match settings.llm_provider:
        case "fixture":
            return FixtureProvider()
        case "ollama":
            return OllamaProvider(
                settings.llm_base_url, settings.llm_model, settings.llm_timeout_seconds
            )
        case "openai_compatible":
            return OpenAICompatibleProvider(
                settings.llm_base_url,
                settings.llm_model,
                settings.llm_api_key,
                settings.llm_timeout_seconds,
            )
