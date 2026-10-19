"""Anthropic Messages API client (REST via httpx)."""

from __future__ import annotations

import os
from typing import Any, ClassVar, Unpack

import httpx

from margin_core.errors import LLMError
from margin_core.llm._http import post_json
from margin_core.llm.base import LLMClient, LLMClientOptions, LLMResponse, Message

DEFAULT_BASE_URL = "https://api.anthropic.com"
API_VERSION = "2023-06-01"


class AnthropicLLM(LLMClient):
    """Client for the Anthropic Messages API. Reads ``ANTHROPIC_API_KEY`` if no key is given."""

    provider: ClassVar[str] = "anthropic"

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        http_client: httpx.AsyncClient | None = None,
        **options: Unpack[LLMClientOptions],
    ) -> None:
        super().__init__(model, **options)
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMError("Anthropic API key missing: set ANTHROPIC_API_KEY or pass api_key")
        self._api_key = key
        self._url = f"{base_url.rstrip('/')}/v1/messages"
        self._http_client = http_client

    async def _complete_raw(
        self,
        messages: list[Message],
        system: str | None,
        max_tokens: int,
        temperature: float | None,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [m.model_dump() for m in messages],
        }
        if system:
            payload["system"] = system
        if temperature is not None:
            payload["temperature"] = temperature
        data = await post_json(
            self._url,
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": API_VERSION,
                "content-type": "application/json",
            },
            payload=payload,
            timeout_s=self.timeout_s,
            client=self._http_client,
        )
        try:
            text = "".join(
                block.get("text", "") for block in data["content"] if block.get("type") == "text"
            )
            usage = data.get("usage", {})
            return LLMResponse(
                text=text,
                model=str(data.get("model", self.model)),
                input_tokens=int(usage.get("input_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
            )
        except (KeyError, TypeError, AttributeError) as exc:
            raise LLMError(f"Unexpected Anthropic response: {exc}") from exc
