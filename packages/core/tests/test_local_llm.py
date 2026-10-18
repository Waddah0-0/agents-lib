"""LocalLLM tests against a fake OpenAI-compatible server (httpx.MockTransport, no network)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from agents_core.config import Settings
from agents_core.errors import LLMError
from agents_core.llm import LocalLLM, MockLLM, create_llm
from pydantic import BaseModel


class Verdict(BaseModel):
    likelihood_ai: float
    reason: str


def _completion(
    content: str, prompt_tokens: int = 10, completion_tokens: int = 5
) -> dict[str, Any]:
    return {
        "model": "qwen2.5:7b",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }


def _client(
    handler: Callable[[httpx.Request], httpx.Response], **kwargs: Any
) -> tuple[LocalLLM, list[dict[str, Any]]]:
    seen: list[dict[str, Any]] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(
            {"url": str(request.url), "headers": request.headers, **json.loads(request.content)}
        )
        return handler(request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(record))
    return LocalLLM("qwen2.5:7b", http_client=http, **kwargs), seen


async def test_complete_sends_openai_compatible_request() -> None:
    llm, seen = _client(lambda _: httpx.Response(200, json=_completion("hello")))
    response = await llm.complete("hi", system="be brief", max_tokens=64)

    assert response.text == "hello"
    assert response.cost_usd == 0.0
    req = seen[0]
    assert req["url"] == "http://localhost:11434/v1/chat/completions"
    assert req["max_tokens"] == 64
    assert req["messages"][0] == {"role": "system", "content": "be brief"}
    assert "response_format" not in req
    assert "authorization" not in req["headers"]
    assert llm.usage.llm_calls == 1
    assert llm.usage.input_tokens == 10


async def test_complete_structured_requests_json_schema() -> None:
    llm, seen = _client(
        lambda _: httpx.Response(200, json=_completion('{"likelihood_ai": 0.2, "reason": "x"}'))
    )
    verdict = await llm.complete_structured(Verdict, "judge this")

    assert verdict == Verdict(likelihood_ai=0.2, reason="x")
    fmt = seen[0]["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["name"] == "Verdict"
    assert fmt["json_schema"]["schema"]["required"] == ["likelihood_ai", "reason"]


async def test_structured_output_can_be_disabled() -> None:
    llm, seen = _client(
        lambda _: httpx.Response(200, json=_completion('{"likelihood_ai": 1, "reason": "y"}')),
        structured_output=False,
    )
    await llm.complete_structured(Verdict, "judge this")
    assert "response_format" not in seen[0]


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("http://localhost:1234", "http://localhost:1234/v1/chat/completions"),
        ("http://localhost:1234/", "http://localhost:1234/v1/chat/completions"),
        ("http://localhost:8080/v1", "http://localhost:8080/v1/chat/completions"),
    ],
)
async def test_base_url_normalization(base_url: str, expected: str) -> None:
    llm, seen = _client(lambda _: httpx.Response(200, json=_completion("ok")), base_url=base_url)
    await llm.complete("hi")
    assert seen[0]["url"] == expected


async def test_api_key_sent_when_configured() -> None:
    llm, seen = _client(lambda _: httpx.Response(200, json=_completion("ok")), api_key="secret")
    await llm.complete("hi")
    assert seen[0]["headers"]["authorization"] == "Bearer secret"


async def test_unreachable_server_fails_fast_with_hint() -> None:
    calls = 0

    def refuse(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("connection refused", request=request)

    llm, _ = _client(refuse, max_retries=3)
    with pytest.raises(LLMError, match="Is it running"):
        await llm.complete("hi")
    assert calls == 1  # no retries when nothing is listening


async def test_missing_model_hint() -> None:
    llm, _ = _client(lambda _: httpx.Response(404, json={"error": "model not found"}))
    with pytest.raises(LLMError, match="ollama pull qwen2.5:7b"):
        await llm.complete("hi")


async def test_budget_never_blocks_local_calls() -> None:
    llm, _ = _client(lambda _: httpx.Response(200, json=_completion("ok")), max_cost_usd=0.0)
    assert (await llm.complete("x" * 100_000)).text == "ok"


def _settings(**values: Any) -> Settings:
    """Settings that ignore any developer .env file."""
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


def test_create_llm_defaults_to_local() -> None:
    llm = create_llm(settings=_settings())
    assert isinstance(llm, LocalLLM)
    assert llm.model == "qwen2.5:7b"
    assert llm.base_url == "http://localhost:11434"


def test_create_llm_uses_settings_for_local() -> None:
    settings = _settings(
        default_llm_model="gemma4:e4b", local_llm_base_url="http://localhost:1234/v1"
    )
    llm = create_llm(settings=settings)
    assert isinstance(llm, LocalLLM)
    assert llm.model == "gemma4:e4b"
    assert llm.base_url == "http://localhost:1234"


def test_default_model_does_not_leak_across_providers() -> None:
    settings = _settings(default_llm_model="gemma4:e4b")
    llm = create_llm(provider="mock", settings=settings)
    assert isinstance(llm, MockLLM)
    assert llm.model == "mock-model"


async def test_mock_records_json_schema() -> None:
    llm = MockLLM(['{"likelihood_ai": 0.5, "reason": "z"}'])
    await llm.complete_structured(Verdict, "judge")
    assert llm.calls[0].json_schema is not None
    assert llm.calls[0].json_schema["title"] == "Verdict"
