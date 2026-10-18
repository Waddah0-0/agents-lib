"""Deterministic LLM client for tests. Never touches the network."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar, Unpack

from agents_core.llm.base import LLMClient, LLMClientOptions, LLMResponse, Message
from agents_core.llm.pricing import FREE

Responder = Callable[[list[Message], str | None], str]


@dataclass(frozen=True)
class MockCall:
    """A recorded call to :class:`MockLLM`."""

    messages: list[Message]
    system: str | None
    max_tokens: int
    json_schema: dict[str, Any] | None = None


class MockLLM(LLMClient):
    """Returns canned responses.

    ``responses`` may be a sequence (consumed in order; an ``Exception`` item is raised
    instead of returned) or a callable ``(messages, system) -> str``. With no responses,
    the last user message is echoed back.
    """

    provider: ClassVar[str] = "mock"

    def __init__(
        self,
        responses: Sequence[str | Exception] | Responder | None = None,
        *,
        model: str = "mock-model",
        **options: Unpack[LLMClientOptions],
    ) -> None:
        options.setdefault("pricing", FREE)
        options.setdefault("backoff_base_s", 0.0)
        super().__init__(model, **options)
        self._responder: Responder | None = None
        self._queue: list[str | Exception] = []
        if callable(responses):
            self._responder = responses
        elif responses is not None:
            self._queue = list(responses)
        self.calls: list[MockCall] = []

    async def _complete_raw(
        self,
        messages: list[Message],
        system: str | None,
        max_tokens: int,
        temperature: float | None,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        self.calls.append(
            MockCall(
                messages=list(messages),
                system=system,
                max_tokens=max_tokens,
                json_schema=json_schema,
            )
        )
        if self._responder is not None:
            text = self._responder(messages, system)
        elif self._queue:
            item = self._queue.pop(0)
            if isinstance(item, Exception):
                raise item
            text = item
        else:
            text = next((m.content for m in reversed(messages) if m.role == "user"), "")
        prompt_chars = sum(len(m.content) for m in messages) + len(system or "")
        return LLMResponse(
            text=text,
            model=self.model,
            input_tokens=math.ceil(prompt_chars / 4),
            output_tokens=math.ceil(len(text) / 4),
        )
