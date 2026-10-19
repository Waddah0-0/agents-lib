"""Saved settings, their place in the order of sources, and the model catalogue."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from margin_core.config import (
    get_settings,
    load_user_config,
    save_user_config,
    setting_sources,
    user_config_path,
)
from margin_core.errors import LLMError
from margin_core.llm import catalog
from margin_core.llm.factory import DEFAULT_MODELS, resolve_model

REAL_CLIENT = httpx.AsyncClient  # tests patch httpx.AsyncClient; keep the real one


@pytest.fixture
def files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    env_file, config = tmp_path / ".env", tmp_path / "cfg" / "settings.json"
    monkeypatch.setenv("MARGIN_ENV_FILE", str(env_file))
    monkeypatch.setenv("MARGIN_CONFIG_FILE", str(config))
    return env_file, config


def test_order_is_environment_then_saved_then_env_file_then_default(
    files: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file, _ = files
    env_file.write_text(
        "DEFAULT_LLM_PROVIDER=openai\nLOCAL_LLM_BASE_URL=http://file:1\nANTHROPIC_API_KEY=\n",
        encoding="utf-8",
    )
    s = get_settings()
    assert (s.default_llm_provider, s.local_llm_base_url) == ("openai", "http://file:1")
    assert s.anthropic_api_key is None  # an empty value in .env is not a key
    assert s.max_cost_usd == 1.0  # default

    save_user_config({"default_llm_provider": "anthropic", "anthropic_api_key": "sk-saved"})
    s = get_settings()
    assert s.default_llm_provider == "anthropic"  # saved beats .env
    assert s.anthropic_api_key is not None and s.anthropic_api_key.get_secret_value() == "sk-saved"

    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "local")
    assert get_settings().default_llm_provider == "local"  # environment beats saved

    sources = setting_sources()
    assert sources["default_llm_provider"] == "environment"
    assert sources["anthropic_api_key"] == "saved"
    assert sources["local_llm_base_url"] == "env_file"
    assert sources["max_cost_usd"] == "default"


def test_saving_merges_removes_and_refuses_unknown_settings(files: tuple[Path, Path]) -> None:
    _, config = files
    save_user_config({"openai_api_key": "sk-1", "openai_model": "m1"})
    save_user_config({"openai_model": "m2", "openai_api_key": None})
    assert load_user_config() == {"openai_model": "m2"}
    assert json.loads(config.read_text(encoding="utf-8")) == {"openai_model": "m2"}
    with pytest.raises(ValueError, match="cannot be saved"):
        save_user_config({"github_token": "x"})  # not something a UI may change
    config.write_text("not json", encoding="utf-8")
    assert load_user_config() == {}  # a broken file counts as empty, never crashes


def test_saving_can_be_turned_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MARGIN_CONFIG_FILE", "")
    assert user_config_path() is None
    with pytest.raises(RuntimeError, match="turned off"):
        save_user_config({"openai_model": "x"})


def test_each_provider_keeps_its_own_model(files: tuple[Path, Path]) -> None:
    save_user_config({"anthropic_model": "claude-x"})
    s = get_settings()
    assert resolve_model("anthropic", s) == "claude-x"
    assert resolve_model("openai", s) == DEFAULT_MODELS["openai"]
    assert resolve_model("local", s) == DEFAULT_MODELS["local"]


def _transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> Callable[..., httpx.AsyncClient]:

    def make(*args: object, **kwargs: object) -> httpx.AsyncClient:
        return REAL_CLIENT(transport=httpx.MockTransport(handler), timeout=5.0)

    return make


async def test_listing_models_asks_each_provider(
    files: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        ids = (
            ["gpt-x", "text-embedding-3", "whisper-1"]
            if "openai" in request.url.host
            else ["b", "a", "nomic-embed-text"]
        )
        return httpx.Response(200, json={"data": [{"id": i} for i in ids]})

    monkeypatch.setattr(httpx, "AsyncClient", _transport(handler))
    save_user_config({"local_llm_base_url": "http://box:1234/v1", "openai_api_key": "sk-o"})
    assert await catalog.list_models("local") == ["a", "b"]
    assert str(seen[-1].url) == "http://box:1234/v1/models"  # the /v1 the user typed is not doubled
    assert await catalog.list_models("openai") == ["gpt-x"]  # embeddings and audio filtered out
    assert seen[-1].headers["authorization"] == "Bearer sk-o"
    with pytest.raises(LLMError, match="Anthropic API key"):
        await catalog.list_models("anthropic")


async def test_listing_models_explains_failures(
    files: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _transport(lambda r: httpx.Response(401)))
    save_user_config({"openai_api_key": "sk-bad"})
    with pytest.raises(LLMError, match="rejected"):
        await catalog.list_models("openai")

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "AsyncClient", _transport(down))
    with pytest.raises(LLMError, match="Can't reach"):
        await catalog.list_models("local")


async def test_connection_check_reports_answer_or_reason(files: tuple[Path, Path]) -> None:
    ok = await catalog.check_connection("mock")
    assert ok.ok and ok.latency_ms is not None and ok.message.startswith("Answered")
    missing = await catalog.check_connection("anthropic")
    assert not missing.ok and "API key" in missing.message
