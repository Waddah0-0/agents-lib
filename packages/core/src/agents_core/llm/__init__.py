"""LLM abstraction: one interface, local and hosted providers, plus a deterministic mock."""

from agents_core.llm.base import LLMClient, LLMClientOptions, LLMResponse, Message, extract_json
from agents_core.llm.factory import DEFAULT_MODELS, create_llm
from agents_core.llm.local import LocalLLM
from agents_core.llm.mock import MockCall, MockLLM
from agents_core.llm.pricing import ModelPricing, lookup_pricing

__all__ = [
    "DEFAULT_MODELS",
    "LLMClient",
    "LLMClientOptions",
    "LLMResponse",
    "LocalLLM",
    "Message",
    "MockCall",
    "MockLLM",
    "ModelPricing",
    "create_llm",
    "extract_json",
    "lookup_pricing",
]
