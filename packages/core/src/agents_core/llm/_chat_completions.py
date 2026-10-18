"""Request/response helpers for the OpenAI Chat Completions wire format.

Shared by the OpenAI client and by local servers that expose an OpenAI-compatible API
(Ollama, LM Studio, llama.cpp, vLLM).
"""

from __future__ import annotations

from typing import Any

from agents_core.errors import LLMError
from agents_core.llm.base import LLMResponse, Message


def chat_messages(messages: list[Message], system: str | None) -> list[dict[str, str]]:
    chat: list[dict[str, str]] = []
    if system:
        chat.append({"role": "system", "content": system})
    chat.extend(m.model_dump() for m in messages)
    return chat


def parse_chat_completion(data: dict[str, Any], default_model: str, provider: str) -> LLMResponse:
    try:
        text = data["choices"][0]["message"].get("content") or ""
        usage = data.get("usage") or {}
        return LLMResponse(
            text=str(text),
            model=str(data.get("model", default_model)),
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
        )
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise LLMError(f"Unexpected {provider} response: {exc}") from exc
