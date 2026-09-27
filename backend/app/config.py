"""Central configuration. All knobs are env-overridable; sane free/local defaults."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AIRE_", extra="ignore")

    # Persistence — SQLite by default so nothing external is required;
    # point at a real Postgres DSN (e.g. via docker-compose) with no code changes.
    database_url: str = "sqlite:///./aire.db"

    # LLM provider chain. "auto" tries gemini -> ollama -> offline, using
    # whichever the environment actually supports. Any single value pins it.
    llm_provider: str = "auto"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"

    # Agent loop budgets (defaults; overridable per incident run).
    max_iterations: int = 15
    max_seconds: int = 120
    max_tokens: int = 60_000

    # Safety: LOW_RISK actions execute automatically when true; HIGH_RISK
    # NEVER auto-executes regardless of this flag.
    auto_approve_low_risk: bool = True
    # Simulation-only escape hatch for headless demos/eval runs. Never wired
    # to anything that touches real infrastructure.
    auto_approve_high_risk_for_eval: bool = False

    # Simulator determinism.
    default_seed: int = 42

    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
