"""LLM abstraction: one interface, local and hosted providers, plus a deterministic mock."""

from margin_core.llm.base import (
    LLMClient,
    LLMClientOptions,
    LLMResponse,
    LLMSession,
    Message,
    extract_json,
)
from margin_core.llm.factory import DEFAULT_MODELS, create_llm
from margin_core.llm.local import LocalLLM
from margin_core.llm.mock import MockCall, MockLLM
from margin_core.llm.pricing import ModelPricing, lookup_pricing

__all__ = [
    "DEFAULT_MODELS",
    "LLMClient",
    "LLMClientOptions",
    "LLMResponse",
    "LLMSession",
    "LocalLLM",
    "Message",
    "MockCall",
    "MockLLM",
    "ModelPricing",
    "create_llm",
    "extract_json",
    "lookup_pricing",
]
