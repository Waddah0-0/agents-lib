"""API server settings, from ``AGENTS_API_*`` environment variables (and ``.env``)."""

from __future__ import annotations

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENTS_API_", extra="ignore")

    host: str = "127.0.0.1"  # not exposed on the network unless you choose to
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    max_body_bytes: int = 1_000_000
    llm_concurrency: int = 1  # runs of agents that use a model (a local model has one GPU)
    other_concurrency: int = 4  # runs of agents that do not
    result_ttl_s: float = 3600.0  # finished runs are forgotten after this
    max_runs: int = 1000  # stored runs, finished ones are dropped oldest first
    event_buffer: int = 200  # progress events kept per run for late subscribers
    cancel_grace_s: float = 30.0  # time a cancelled run gets to stop on its own


def load_settings() -> ApiSettings:
    env_file = os.environ.get("AGENTS_LIB_ENV_FILE", ".env")
    return ApiSettings(_env_file=env_file or None)  # type: ignore[call-arg]
