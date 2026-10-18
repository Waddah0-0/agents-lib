"""Build an LLM client from a provider name and settings."""

from __future__ import annotations

from agents_core.config import Settings, get_settings
from agents_core.errors import LLMError
from agents_core.llm.anthropic import AnthropicLLM
from agents_core.llm.base import LLMClient
from agents_core.llm.local import LocalLLM
from agents_core.llm.mock import MockLLM
from agents_core.llm.openai import OpenAILLM

DEFAULT_MODELS: dict[str, str] = {
    "local": "qwen2.5:7b",
    "anthropic": "claude-sonnet-4-5",
    "openai": "gpt-4.1-mini",
    "mock": "mock-model",
}


def create_llm(
    provider: str | None = None,
    model: str | None = None,
    *,
    max_cost_usd: float | None = None,
    settings: Settings | None = None,
) -> LLMClient:
    """Create a client. Missing values fall back to settings, then to ``DEFAULT_MODELS``.

    ``DEFAULT_LLM_MODEL`` only applies to ``DEFAULT_LLM_PROVIDER``, so overriding the
    provider never pairs it with another provider's model.
    """
    settings = settings or get_settings()
    default_provider = settings.default_llm_provider.lower()
    provider = (provider or default_provider).lower()
    if provider not in DEFAULT_MODELS:
        raise LLMError(f"Unknown LLM provider {provider!r}; choose from {sorted(DEFAULT_MODELS)}")
    settings_model = settings.default_llm_model if provider == default_provider else None
    model = model or settings_model or DEFAULT_MODELS[provider]
    budget = max_cost_usd if max_cost_usd is not None else settings.max_cost_usd

    if provider == "local":
        local_key = settings.local_llm_api_key
        return LocalLLM(
            model,
            base_url=settings.local_llm_base_url,
            api_key=local_key.get_secret_value() if local_key else None,
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
