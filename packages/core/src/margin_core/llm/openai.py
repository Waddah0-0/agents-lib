"""OpenAI Chat Completions client (REST via httpx)."""

from __future__ import annotations

import os
from typing import Any, ClassVar, Unpack

import httpx

from margin_core.errors import LLMError
from margin_core.llm._chat_completions import chat_messages, parse_chat_completion
from margin_core.llm._http import post_json
from margin_core.llm.base import LLMClient, LLMClientOptions, LLMResponse, Message

DEFAULT_BASE_URL = "https://api.openai.com"


class OpenAILLM(LLMClient):
    """Client for OpenAI Chat Completions. Reads ``OPENAI_API_KEY`` if no key is given."""

    provider: ClassVar[str] = "openai"

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
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise LLMError("OpenAI API key missing: set OPENAI_API_KEY or pass api_key")
        self._api_key = key
        self._url = f"{base_url.rstrip('/')}/v1/chat/completions"
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
            "messages": chat_messages(messages, system),
            "max_completion_tokens": max_tokens,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        data = await post_json(
            self._url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            payload=payload,
            timeout_s=self.timeout_s,
            client=self._http_client,
        )
        return parse_chat_completion(data, self.model, "OpenAI")
