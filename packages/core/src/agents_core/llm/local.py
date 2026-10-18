"""Client for locally hosted models behind an OpenAI-compatible API.

Works with Ollama (default, ``http://localhost:11434``), LM Studio (``:1234``),
llama.cpp ``llama-server`` (``:8080``) and vLLM (``:8000``). Calls are free, so pricing is
zero and the budget cap never triggers; timeouts are longer because the first call may
have to load the model into memory.
"""

from __future__ import annotations

import os
from typing import Any, ClassVar, Unpack

import httpx

from agents_core.errors import LLMError, TransientLLMError
from agents_core.llm._chat_completions import chat_messages, parse_chat_completion
from agents_core.llm._http import post_json
from agents_core.llm.base import LLMClient, LLMClientOptions, LLMResponse, Message
from agents_core.llm.pricing import FREE

DEFAULT_BASE_URL = "http://localhost:11434"


def _normalize_base_url(base_url: str) -> str:
    url = base_url.strip().rstrip("/")
    return url[: -len("/v1")] if url.endswith("/v1") else url


class LocalLLM(LLMClient):
    """Client for a local OpenAI-compatible server. Reads ``LOCAL_LLM_BASE_URL`` if set.

    With ``structured_output=True`` (default), :meth:`complete_structured` requests
    schema-constrained decoding via ``response_format``, which makes small models far more
    reliable at emitting valid JSON. Disable it for servers that reject that field.
    """

    provider: ClassVar[str] = "local"

    def __init__(
        self,
        model: str,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        structured_output: bool = True,
        http_client: httpx.AsyncClient | None = None,
        **options: Unpack[LLMClientOptions],
    ) -> None:
        options.setdefault("pricing", FREE)
        options.setdefault("timeout_s", 300.0)
        options.setdefault("max_retries", 1)
        super().__init__(model, **options)
        self.base_url = _normalize_base_url(
            base_url or os.environ.get("LOCAL_LLM_BASE_URL") or DEFAULT_BASE_URL
        )
        self._url = f"{self.base_url}/v1/chat/completions"
        self._api_key = api_key  # only for servers started with an API key (e.g. vLLM)
        self.structured_output = structured_output
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
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if json_schema is not None and self.structured_output:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": json_schema.get("title", "response"),
                    "schema": json_schema,
                },
            }
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            data = await post_json(
                self._url,
                headers=headers,
                payload=payload,
                timeout_s=self.timeout_s,
                client=self._http_client,
            )
        except TransientLLMError as exc:
            if isinstance(exc.__cause__, httpx.ConnectError):
                # Not worth retrying: nothing is listening.
                raise LLMError(
                    f"Cannot reach a local LLM server at {self.base_url}. Is it running? "
                    "(Ollama: `ollama serve`; or set LOCAL_LLM_BASE_URL)"
                ) from exc
            raise
        except LLMError as exc:
            if "HTTP 404" in str(exc):
                raise LLMError(
                    f"{exc}\nModel {self.model!r} may not be available locally "
                    f"(Ollama: `ollama pull {self.model}`)"
                ) from exc
            raise
        return parse_chat_completion(data, self.model, "local LLM")
