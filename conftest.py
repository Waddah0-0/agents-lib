"""Workspace-wide test setup: tests never depend on the developer's environment."""

from __future__ import annotations

import pytest

ISOLATED_VARS = (
    "DEFAULT_LLM_PROVIDER",
    "DEFAULT_LLM_MODEL",
    "MAX_COST_USD",
    "LOCAL_LLM_BASE_URL",
    "LOCAL_LLM_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GITHUB_TOKEN",
    "LOG_LEVEL",
)


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ISOLATED_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MARGIN_ENV_FILE", "")  # never read a developer's .env
