"""Centralized, environment-driven configuration.

All settings are read from environment variables prefixed with ``INSIGHTFORGE_``
(or a local ``.env`` file, which is git-ignored). Nothing secret has a default.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INSIGHTFORGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    api_host: str = "127.0.0.1"
    api_port: int = 8111
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3101"])

    # Storage
    data_dir: Path = Path("./var")
    max_upload_bytes: int = 50 * 1024 * 1024

    # LLM provider: "ollama" (local), "openai_compatible", or "fixture" (deterministic tests)
    llm_provider: Literal["ollama", "openai_compatible", "fixture"] = "ollama"
    llm_base_url: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen3:4b-instruct"
    llm_api_key: str | None = None
    llm_timeout_seconds: float = 120.0

    # Query execution limits (enforced in the sandbox worker)
    query_timeout_seconds: float = 10.0
    query_max_rows: int = 10_000
    sandbox_memory_mb: int = 1024

    @property
    def datasets_dir(self) -> Path:
        return self.data_dir / "datasets"

    @property
    def metadata_db_path(self) -> Path:
        return self.data_dir / "insightforge.sqlite3"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
