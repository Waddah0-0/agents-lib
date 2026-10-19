"""Background runs: an in-memory store, two concurrency pools, events and cancellation.

A run moves through ``queued -> running -> done`` (or ``cancelled``). A run whose agent
fails still ends as ``done``: the failure is in its result (``status="error"``), not in the
run's state. Progress events are numbered and kept in a bounded buffer, so a client that
connects late (or reconnects) gets everything it missed.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from collections import deque
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from agents_core import AgentRegistry, AgentResult, BaseAgent, ProgressEvent, RunContext
from agents_core.llm import LLMClient
from agents_core.logging import get_logger
from pydantic import BaseModel

from agents_api.settings import ApiSettings

RunStatus = Literal["queued", "running", "done", "cancelled"]
FINISHED: frozenset[str] = frozenset({"done", "cancelled"})
logger = get_logger("api.jobs")


@dataclass
class RunEvent:
    seq: int
    kind: Literal["status", "progress", "result"]
    data: dict[str, Any]


@dataclass
class Run:
    id: str
    agent_id: str
    pool: str
    status: RunStatus = "queued"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress: ProgressEvent | None = None
    result: AgentResult | None = None
    events: deque[RunEvent] = field(default_factory=deque)
    token: Any = None  # CancellationToken, set when created
    task: asyncio.Task[None] | None = None
    finished_monotonic: float | None = None
    _seq: int = 0
    _changed: asyncio.Event = field(default_factory=asyncio.Event)

    def add_event(
        self, kind: Literal["status", "progress", "result"], data: dict[str, Any]
    ) -> None:
        self._seq += 1
        self.events.append(RunEvent(self._seq, kind, data))
        # wake every waiting subscriber, then arm a fresh event for the next change
        self._changed.set()
        self._changed = asyncio.Event()


class _Pool:
    """A FIFO concurrency limit that can report queue positions."""

    def __init__(self, size: int) -> None:
        self.semaphore = asyncio.Semaphore(size)
        self.waiting: deque[str] = deque()

    def position(self, run_id: str) -> int | None:
        try:
            return self.waiting.index(run_id) + 1
        except ValueError:
            return None


class RunManager:
    def __init__(
        self,
        registry: AgentRegistry,
        settings: ApiSettings,
        llm_factory: Callable[[], LLMClient | None] | None = None,
    ) -> None:
        self.registry = registry
        self.settings = settings
        self.runs: dict[str, Run] = {}
        self.pools = {
            "llm": _Pool(settings.llm_concurrency),
            "other": _Pool(settings.other_concurrency),
        }
        self._llm_factory = llm_factory
        self._llm: LLMClient | None = None
        self._llm_ready = False
        self._sweeper: asyncio.Task[None] | None = None

    # ---- lifecycle ------------------------------------------------------------------

    async def start(self) -> None:
        self._sweeper = asyncio.create_task(self._sweep_forever())

    async def stop(self) -> None:
        if self._sweeper is not None:
            self._sweeper.cancel()
        for run in self.runs.values():
            if run.task is not None and not run.task.done():
                run.task.cancel()

    def _client(self) -> LLMClient | None:
        """One shared client; every run gets its own session from it (usage, budget)."""
        if not self._llm_ready:
            self._llm_ready = True
            if self._llm_factory is not None:
                try:
                    self._llm = self._llm_factory()
                except Exception:  # noqa: BLE001 - a missing key must not break the API
                    logger.warning("No LLM client could be created", exc_info=True)
        return self._llm

    # ---- runs -----------------------------------------------------------------------

    def submit(self, agent_cls: type[BaseAgent], parsed: BaseModel) -> Run:
        from agents_core import CancellationToken

        pool = "llm" if agent_cls.uses_llm else "other"
        run = Run(id=uuid.uuid4().hex, agent_id=agent_cls.id, pool=pool)
        run.token = CancellationToken()
        run.events = deque(maxlen=self.settings.event_buffer)
        self.runs[run.id] = run
        self.pools[pool].waiting.append(run.id)
        run.add_event("status", {"status": "queued"})
        run.task = asyncio.create_task(self._execute(run, agent_cls, parsed))
        self._enforce_capacity()
        return run

    def get(self, run_id: str) -> Run | None:
        return self.runs.get(run_id)

    def queue_position(self, run: Run) -> int | None:
        return self.pools[run.pool].position(run.id) if run.status == "queued" else None

    async def _execute(self, run: Run, agent_cls: type[BaseAgent], parsed: BaseModel) -> None:
        pool = self.pools[run.pool]
        try:
            async with pool.semaphore:
                with contextlib.suppress(ValueError):
                    pool.waiting.remove(run.id)
                if run.token.cancelled:
                    self._finish(run, None, cancelled=True)
                    return
                run.status = "running"
                run.started_at = datetime.now(UTC)
                run.add_event("status", {"status": "running"})

                def on_progress(event: ProgressEvent) -> None:
                    run.progress = event
                    run.add_event("progress", event.model_dump(mode="json"))

                agent = agent_cls(llm=self._client())
                ctx = RunContext(progress=on_progress, cancel_token=run.token)
                result = await agent.execute(parsed, ctx)
                self._finish(run, result, cancelled=run.token.cancelled)
        except asyncio.CancelledError:
            self._finish(run, None, cancelled=True)
        except Exception as exc:  # noqa: BLE001 - never lose a run silently
            logger.exception("Run %s crashed outside the agent", run.id)
            self._finish(
                run,
                AgentResult(
                    agent_id=run.agent_id,
                    agent_version="unknown",
                    status="error",
                    summary="The server failed to run this agent.",
                    error=str(exc),
                ),  # fmt: skip
                cancelled=False,
            )

    def _finish(self, run: Run, result: AgentResult | None, *, cancelled: bool) -> None:
        if run.status in FINISHED:
            return
        with contextlib.suppress(ValueError):
            self.pools[run.pool].waiting.remove(run.id)
        run.status = "cancelled" if cancelled else "done"
        run.result = result
        run.finished_at = datetime.now(UTC)
        run.finished_monotonic = time.monotonic()
        run.add_event("status", {"status": run.status})
        run.add_event(
            "result",
            {"status": run.status, "result": result.model_dump(mode="json") if result else None},
        )

    async def cancel(self, run: Run) -> None:
        """Ask the run to stop; force it after the grace period."""
        if run.status in FINISHED:
            return
        run.token.cancel()
        if run.status == "queued":
            if run.task is not None:
                run.task.cancel()
            self._finish(run, None, cancelled=True)
            return
        asyncio.create_task(self._force_after_grace(run))

    async def _force_after_grace(self, run: Run) -> None:
        await asyncio.sleep(self.settings.cancel_grace_s)
        if run.status not in FINISHED and run.task is not None:
            logger.warning("Run %s ignored cancellation; stopping its task", run.id)
            run.task.cancel()

    # ---- events ---------------------------------------------------------------------

    async def events(self, run: Run, after: int = 0) -> AsyncIterator[RunEvent]:
        """Yield events with ``seq > after`` (buffered first), until the result event."""
        while True:
            pending = [e for e in list(run.events) if e.seq > after]
            for event in pending:
                yield event
                after = event.seq
                if event.kind == "result":
                    return
            if run.status in FINISHED and not pending:
                return
            await run._changed.wait()

    # ---- housekeeping -----------------------------------------------------------------

    def _enforce_capacity(self) -> None:
        finished = sorted(
            (r for r in self.runs.values() if r.status in FINISHED),
            key=lambda r: r.finished_monotonic or 0.0,
        )
        while len(self.runs) > self.settings.max_runs and finished:
            self.runs.pop(finished.pop(0).id, None)

    def sweep(self) -> int:
        """Forget finished runs older than the TTL. Returns how many were removed."""
        now = time.monotonic()
        expired = [
            r.id for r in self.runs.values()
            if r.finished_monotonic is not None
            and now - r.finished_monotonic > self.settings.result_ttl_s
        ]  # fmt: skip
        for run_id in expired:
            self.runs.pop(run_id, None)
        return len(expired)

    async def _sweep_forever(self) -> None:
        while True:
            await asyncio.sleep(max(1.0, min(60.0, self.settings.result_ttl_s)))
            self.sweep()
