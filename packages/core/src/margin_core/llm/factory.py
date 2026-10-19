"""Build an LLM client from a provider name and settings."""

from __future__ import annotations

from margin_core.config import Settings, get_settings
from margin_core.errors import LLMError
from margin_core.llm.anthropic import AnthropicLLM
from margin_core.llm.base import LLMClient
from margin_core.llm.local import LocalLLM
from margin_core.llm.mock import MockLLM
from margin_core.llm.openai import OpenAILLM

DEFAULT_MODELS: dict[str, str] = {
    "local": "qwen3.5:9b",  # chosen by eval/tools/compare_judges.py (2026-10-19)
    "anthropic": "claude-sonnet-5-5",
    "openai": "gpt-4.1-mini",
    "mock": "mock-model",
}


PROVIDER_MODEL_SETTING: dict[str, str] = {
    "local": "local_llm_model",
    "anthropic": "anthropic_model",
    "openai": "openai_model",
}


def resolve_model(provider: str, settings: Settings) -> str:
    """The model to use with ``provider``: its own setting, then ``DEFAULT_LLM_MODEL`` (which
    only applies to the default provider, so it never pairs with another provider), then the
    built-in default."""
    provider = provider.lower()
    field = PROVIDER_MODEL_SETTING.get(provider)
    own = getattr(settings, field) if field else None
    shared = (
        settings.default_llm_model if provider == settings.default_llm_provider.lower() else None
    )
    return own or shared or DEFAULT_MODELS[provider]


def create_llm(
    provider: str | None = None,
    model: str | None = None,
    *,
    max_cost_usd: float | None = None,
    settings: Settings | None = None,
) -> LLMClient:
    """Create a client. Missing values fall back to settings, then to ``DEFAULT_MODELS``."""
    settings = settings or get_settings()
    provider = (provider or settings.default_llm_provider).lower()
    if provider not in DEFAULT_MODELS:
        raise LLMError(f"Unknown LLM provider {provider!r}; choose from {sorted(DEFAULT_MODELS)}")
    model = model or resolve_model(provider, settings)
    budget = max_cost_usd if max_cost_usd is not None else settings.max_cost_usd

    if provider == "local":
        local_key = settings.local_llm_api_key
        return LocalLLM(
            model,
            base_url=settings.local_llm_base_url,
            api_key=local_key.get_secret_value() if local_key else None,
            reasoning_effort=settings.local_llm_reasoning_effort,
            max_cost_usd=budget,
        )
    if provider == "anthropic":
        key = settings.anthropic_api_key
        return AnthropicLLM(
            model, api_key=key.get_secret_value() if key else None, max_cost_usd=budget
        )
    if provider == "openai":
        key = settings.openai_api_key
        return OpenAILLM(
            model, api_key=key.get_secret_value() if key else None, max_cost_usd=budget
        )
    return MockLLM(model=model, max_cost_usd=budget)
