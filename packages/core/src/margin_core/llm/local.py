"""Client for locally hosted models behind an OpenAI-compatible API.

Works with Ollama (default, ``http://localhost:11434``), LM Studio (``:1234``),
llama.cpp ``llama-server`` (``:8080``) and vLLM (``:8000``). Calls are free, so pricing is
zero and the budget cap never triggers; timeouts are longer because the first call may
have to load the model into memory.

OpenAI-compatible servers silently truncate prompts that exceed the model's context window.
For Ollama the window is read from ``/api/ps`` (an overflowing prompt is reported as exactly
the window size); for other servers a ratio heuristic catches gross truncation. Either way
the response carries a warning instead of failing.
"""

from __future__ import annotations

import os
from typing import Any, ClassVar, Unpack

import httpx

from margin_core.errors import LLMError, TransientLLMError
from margin_core.llm._chat_completions import chat_messages, parse_chat_completion
from margin_core.llm._http import post_json
from margin_core.llm.base import LLMClient, LLMClientOptions, LLMResponse, Message
from margin_core.llm.pricing import FREE

DEFAULT_BASE_URL = "http://localhost:11434"

# Fallback truncation heuristic for servers that do not report their context window. Code
# averages about 3 characters per token, so a reported count below 0.6 x (chars / 4) means
# a large share of the prompt was dropped.
TRUNCATION_RATIO = 0.6
MIN_CHARS_FOR_RATIO_CHECK = 4000
MAX_CONTEXT_PROBES = 3


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
        reasoning_effort: str | None = "none",
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
        # Thinking models (e.g. qwen3.5) otherwise spend the whole output budget on hidden
        # reasoning. "none" turns it off; other models ignore the field (verified 2026-10-19).
        self.reasoning_effort = reasoning_effort or None
        self._http_client = http_client
        self._context_window: int | None = None
        self._context_probes_left = MAX_CONTEXT_PROBES

    async def context_window(self) -> int | None:
        """Context window of the loaded model (Ollama only), cached once known."""
        if self._context_window is None and self._context_probes_left > 0:
            self._context_probes_left -= 1
            self._context_window = await self._probe_context_window()
        return self._context_window

    async def _probe_context_window(self) -> int | None:
        url = f"{self.base_url}/api/ps"
        try:
            if self._http_client is not None:
                response = await self._http_client.get(url, timeout=5.0)
            else:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(url)
        except httpx.HTTPError:
            self._context_probes_left = 0
            return None
        if response.status_code != 200:
            self._context_probes_left = 0  # not Ollama; it will not start answering later
            return None
        try:
            models = response.json().get("models") or []
        except ValueError:
            self._context_probes_left = 0
            return None
        names = {self.model, f"{self.model}:latest"}
        for entry in models:
            if isinstance(entry, dict) and (
                entry.get("name") in names or entry.get("model") in names
            ):
                window = entry.get("context_length")
                return window if isinstance(window, int) and window > 0 else None
        return None  # model not loaded yet; probe again after a later call

    async def _truncation_warning(self, prompt_chars: int, prompt_tokens: int) -> str | None:
        window = await self.context_window()
        if window is not None:
            if prompt_tokens >= window:
                return (
                    f"A prompt filled the local model's whole context window ({window} tokens) "
                    "and was probably truncated. Raise the window (Ollama: "
                    "OLLAMA_CONTEXT_LENGTH) or send less text."
                )
            return None
        expected = prompt_chars / 4
        if (
            prompt_chars >= MIN_CHARS_FOR_RATIO_CHECK
            and prompt_tokens < TRUNCATION_RATIO * expected
        ):
            return (
                "A prompt was probably truncated by the local LLM server (it counted far fewer "
                "tokens than were sent). Raise the server's context window or send less text."
            )
        return None

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
        if self.reasoning_effort is not None:
            payload["reasoning_effort"] = self.reasoning_effort
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
        response = parse_chat_completion(data, self.model, "local LLM")
        message = (data.get("choices") or [{}])[0].get("message") or {}
        if not response.text and (message.get("reasoning") or message.get("reasoning_content")):
            raise LLMError(
                f"{self.model} spent its whole output on hidden reasoning and gave no answer. "
                "Set LOCAL_LLM_REASONING_EFFORT=none (the default) or raise max_tokens."
            )
        prompt_chars = sum(len(m.content) for m in messages) + len(system or "")
        warning = await self._truncation_warning(prompt_chars, response.input_tokens)
        if warning:
            response = response.model_copy(update={"warnings": [*response.warnings, warning]})
        return response
