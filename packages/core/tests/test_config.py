from __future__ import annotations

from pathlib import Path

import pytest
from agents_core.config import get_settings


def test_defaults_without_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text("DEFAULT_LLM_MODEL=from-dotenv\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    settings = get_settings()  # the autouse fixture disables env files
    assert settings.default_llm_provider == "local"
    assert settings.default_llm_model is None


def test_env_file_can_be_chosen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / "custom.env"
    env.write_text("DEFAULT_LLM_MODEL=from-file\n", encoding="utf-8")
    monkeypatch.setenv("AGENTS_LIB_ENV_FILE", str(env))
    assert get_settings().default_llm_model == "from-file"


def test_environment_variables_win(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "mock")
    assert get_settings().default_llm_provider == "mock"
