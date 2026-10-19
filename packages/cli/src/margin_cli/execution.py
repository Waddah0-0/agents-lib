"""Running an agent from the CLI: LLM setup, progress display and Ctrl+C handling."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from margin_core import AgentResult, BaseAgent, ProgressEvent, RunContext
from margin_core.config import Settings
from margin_core.errors import LLMError
from margin_core.llm import LLMClient, create_llm
from pydantic import BaseModel
from rich.console import Console

CANCEL_GRACE_S = 5.0
"""How long a cancelled agent gets to stop on its own before its task is cancelled."""


class ExplicitLLMError(Exception):
    """The user asked for a specific provider or model, and it cannot be set up."""


def make_llm(
    provider: str | None, model: str | None, max_cost_usd: float, settings: Settings
) -> LLMClient | None:
    """Create the LLM client for a run.

    Creating a client never contacts the server, so the default (local) client is always
    created and only used if the agent asks for it. If the default provider cannot be set
    up (e.g. a hosted provider without an API key), the run continues without an LLM and
    agents that need one fail with a clear error. If the user chose ``--provider`` or
    ``--model`` explicitly, any problem is reported straight away.
    """
    try:
        return create_llm(provider, model, max_cost_usd=max_cost_usd, settings=settings)
    except LLMError as exc:
        if provider is not None or model is not None:
            raise ExplicitLLMError(str(exc)) from exc
        return None


async def execute_cancellable(
    agent: BaseAgent,
    parsed_input: BaseModel,
    ctx: RunContext,
    *,
    grace_s: float = CANCEL_GRACE_S,
) -> AgentResult | None:
    """Run the agent; if this task is cancelled (Ctrl+C), cancel cooperatively.

    The agent gets ``grace_s`` seconds to notice the cancellation token and return its own
    result. After that its task is cancelled and ``None`` is returned.
    """
    task = asyncio.ensure_future(agent.execute(parsed_input, ctx))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        current = asyncio.current_task()
        if current is not None:
            current.uncancel()  # we handle the cancellation ourselves
        ctx.cancel_token.cancel()
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=grace_s)
        except (TimeoutError, asyncio.CancelledError):
            task.cancel()
            return None


class ProgressDisplay:
    """A one-line spinner on stderr, driven by the agent's progress events."""

    def __init__(self, console: Console, agent_name: str, enabled: bool) -> None:
        self._console = console
        self._agent_name = agent_name
        self._enabled = enabled and console.is_terminal
        self._status: Any = None

    def __enter__(self) -> Callable[[ProgressEvent], None] | None:
        if not self._enabled:
            return None
        self._status = self._console.status(f"{self._agent_name}: starting")
        self._status.__enter__()
        return self.update

    def update(self, event: ProgressEvent) -> None:
        text = f"{self._agent_name}: {event.stage}"
        if event.message:
            text += f" - {event.message}"
        if event.fraction is not None:
            text += f" ({event.fraction:.0%})"
        if self._status is not None:
            self._status.update(text)

    def __exit__(self, *exc: object) -> None:
        if self._status is not None:
            self._status.__exit__(None, None, None)
            self._status = None
