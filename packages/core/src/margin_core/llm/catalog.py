"""What a UI needs to set up a model: the providers, the models each one offers right now
(asked live, so the list never goes stale), and a quick connection check."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

import httpx

from margin_core.config import Settings, get_settings
from margin_core.errors import LLMError
from margin_core.llm import anthropic, openai
from margin_core.llm.factory import DEFAULT_MODELS, create_llm, resolve_model
from margin_core.llm.local import _normalize_base_url


def readable_error(exc: Exception) -> str:
    """The useful part of an LLM error: the server's own message when it sent JSON, plus a
    hint for the common case of a local model that does not fit in memory."""
    text = str(exc).strip()
    match = re.search(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    message = match.group(1) if match else text
    if "requires more system memory" in message:
        message += " (close other programs, or use a smaller model)"
    return message


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    needs_key: bool
    on_device: bool  # False: prompts (for the detector, samples of your code) leave the machine


PROVIDERS: tuple[Provider, ...] = (
    Provider("local", "Local server (Ollama, LM Studio, llama.cpp, vLLM)", False, True),
    Provider("anthropic", "Anthropic", True, False),
    Provider("openai", "OpenAI", True, False),
)
PROVIDER_IDS = frozenset(p.id for p in PROVIDERS)

# OpenAI's list includes embedding, audio and image models; keep the ones that chat
_OPENAI_NOT_CHAT = ("embedding", "whisper", "tts", "dall-e", "audio", "realtime", "transcribe",
                    "image", "moderation", "search", "davinci", "babbage")  # fmt: skip


def _key(secret: object) -> str | None:
    value = getattr(secret, "get_secret_value", lambda: None)()
    return value or None


async def list_models(
    provider: str, settings: Settings | None = None, timeout_s: float = 10.0
) -> list[str]:
    """Model ids the provider offers, sorted. Raises LLMError with a readable message."""
    settings = settings or get_settings()
    if provider == "local":
        base = _normalize_base_url(settings.local_llm_base_url)
        url, headers = f"{base}/v1/models", {}
        if key := _key(settings.local_llm_api_key):
            headers["Authorization"] = f"Bearer {key}"
    elif provider == "anthropic":
        key = _key(settings.anthropic_api_key)
        if not key:
            raise LLMError("Add an Anthropic API key first.")
        url = f"{anthropic.DEFAULT_BASE_URL}/v1/models?limit=100"
        headers = {"x-api-key": key, "anthropic-version": anthropic.API_VERSION}
    elif provider == "openai":
        key = _key(settings.openai_api_key)
        if not key:
            raise LLMError("Add an OpenAI API key first.")
        url, headers = f"{openai.DEFAULT_BASE_URL}/v1/models", {"Authorization": f"Bearer {key}"}
    else:
        raise LLMError(f"Unknown provider {provider!r}")

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        where = settings.local_llm_base_url if provider == "local" else provider
        raise LLMError(f"Can't reach {where}. Is it running, and is the address right?") from exc
    if response.status_code in (401, 403):
        raise LLMError("The API key was rejected.")
    if response.status_code >= 400:
        raise LLMError(f"The server answered {response.status_code} when asked for its models.")
    try:
        ids = [str(m["id"]) for m in response.json().get("data", [])]
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise LLMError("The server's model list was not in the expected format.") from exc
    if provider == "openai":
        ids = [i for i in ids if not any(word in i for word in _OPENAI_NOT_CHAT)]
    elif provider == "local":
        ids = [i for i in ids if "embed" not in i.lower()]  # embedding models cannot chat
    return sorted(set(ids))


@dataclass(frozen=True)
class ConnectionCheck:
    ok: bool
    provider: str
    model: str
    latency_ms: int | None
    message: str


async def check_connection(
    provider: str | None = None, model: str | None = None, settings: Settings | None = None
) -> ConnectionCheck:
    """Send one tiny prompt and report whether, and how fast, the model answered."""
    settings = settings or get_settings()
    provider = (provider or settings.default_llm_provider).lower()
    model = model or (resolve_model(provider, settings) if provider in DEFAULT_MODELS else "")
    started = time.monotonic()
    try:
        llm = create_llm(provider, model, settings=settings, max_cost_usd=0.05)
        reply = await llm.complete("Reply with the single word OK.", max_tokens=16)
    except LLMError as exc:
        return ConnectionCheck(
            False, provider, model, None, readable_error(exc) or "The call failed."
        )
    latency = int((time.monotonic() - started) * 1000)
    answered = reply.text.strip()[:40] or "(an empty answer)"
    return ConnectionCheck(True, provider, model, latency, f"Answered “{answered}”.")
