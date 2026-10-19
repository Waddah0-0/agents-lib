"""The FastAPI application: list agents, start runs, follow them live, cancel them."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable, MutableMapping
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from margin_core import (
    AgentInfo,
    AgentLoadError,
    AgentNotFoundError,
    AgentRegistry,
    AgentResult,
    BaseAgent,
    InputValidationError,
    ProgressEvent,
    default_registry,
)
from margin_core.llm import LLMClient, create_llm
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from margin_api import __version__
from margin_api.jobs import Run, RunManager, RunStatus
from margin_api.settings import ApiSettings, load_settings

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]


class AgentList(BaseModel):
    agents: list[AgentInfo]
    load_errors: dict[str, str] = Field(
        default_factory=dict, description="Installed agents that failed to load, and why."
    )


class RunCreated(BaseModel):
    run_id: str
    status: RunStatus
    queue_position: int | None
    links: dict[str, str]


class RunView(BaseModel):
    run_id: str
    agent_id: str
    status: RunStatus
    queue_position: int | None = Field(description="1 = next to start; null unless queued.")
    progress: ProgressEvent | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    result: AgentResult | None = Field(description="Present once the run is done.")


class _BodyLimit:
    """Reject request bodies over ``limit`` bytes with 413, including chunked uploads.

    The body is read here (it is small by definition) and replayed to the app, because an
    error raised while the app reads its body would be reported as a generic 400.
    """

    def __init__(self, app: Any, limit: int) -> None:
        self.app = app
        self.limit = limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") in {"GET", "HEAD", "DELETE", "OPTIONS"}:
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.limit:
            await self._reject(send)
            return
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.limit:
                await self._reject(send)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    async def _reject(self, send: Send) -> None:
        body = json.dumps({"detail": f"Request body exceeds {self.limit} bytes"}).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json")]})  # fmt: skip
        await send({"type": "http.response.body", "body": body})


def _default_llm() -> LLMClient | None:
    return create_llm()


def create_app(
    *,
    registry: AgentRegistry | None = None,
    settings: ApiSettings | None = None,
    llm_factory: Callable[[], LLMClient | None] | None = _default_llm,
) -> FastAPI:
    settings = settings or load_settings()
    registry = registry or default_registry()
    manager = RunManager(registry, settings, llm_factory)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await manager.start()
        try:
            yield
        finally:
            await manager.stop()

    app = FastAPI(
        title="margin API",
        version=__version__,
        description=(
            "Run any installed margin agent over HTTP. Runs are asynchronous: start one, "
            "then poll it or follow its events (server-sent events) until the result arrives."
        ),
        lifespan=lifespan,
    )
    app.state.manager = manager
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "Last-Event-ID"],
    )
    app.add_middleware(_BodyLimit, limit=settings.max_body_bytes)

    def agent_class(agent_id: str) -> type[BaseAgent]:
        try:
            return registry.get_agent_class(agent_id)
        except AgentNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except AgentLoadError as exc:
            raise HTTPException(500, f"Agent {agent_id!r} failed to load: {exc}") from exc

    def find_run(run_id: str) -> Run:
        run = manager.get(run_id)
        if run is None:
            raise HTTPException(404, f"No run {run_id!r} (unknown, or expired)")
        return run

    def view(run: Run) -> RunView:
        return RunView(
            run_id=run.id, agent_id=run.agent_id, status=run.status,
            queue_position=manager.queue_position(run), progress=run.progress,
            created_at=run.created_at, started_at=run.started_at,
            finished_at=run.finished_at, result=run.result,
        )  # fmt: skip

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/agents", response_model=AgentList, tags=["agents"])
    def list_agents() -> AgentList:
        return AgentList(agents=registry.list_agents(), load_errors=registry.load_errors)

    @app.get("/agents/{agent_id}", response_model=AgentInfo, tags=["agents"])
    def get_agent(agent_id: str) -> AgentInfo:
        return agent_class(agent_id).info()

    @app.post(
        "/agents/{agent_id}/runs",
        status_code=202,
        response_model=RunCreated,
        tags=["runs"],
        responses={422: {"description": "The input does not match the agent's input schema"}},
    )
    async def start_run(agent_id: str, body: dict[str, Any]) -> RunCreated:
        cls = agent_class(agent_id)
        try:
            parsed = cls.parse_input(body)
        except InputValidationError as exc:
            raise HTTPException(422, str(exc)) from exc
        run = manager.submit(cls, parsed)
        return RunCreated(
            run_id=run.id,
            status=run.status,
            queue_position=manager.queue_position(run),
            links={"self": f"/runs/{run.id}", "events": f"/runs/{run.id}/events"},
        )

    @app.get("/runs/{run_id}", response_model=RunView, tags=["runs"])
    def get_run(run_id: str) -> RunView:
        return view(find_run(run_id))

    @app.get("/runs", response_model=list[RunView], tags=["runs"])
    def list_runs(limit: int = 50) -> list[RunView]:
        runs = sorted(manager.runs.values(), key=lambda r: r.created_at, reverse=True)
        return [view(r) for r in runs[: max(1, min(limit, 500))]]

    @app.delete("/runs/{run_id}", response_model=RunView, status_code=202, tags=["runs"])
    async def cancel_run(run_id: str) -> RunView:
        run = find_run(run_id)
        await manager.cancel(run)
        return view(run)

    @app.get(
        "/runs/{run_id}/events",
        tags=["runs"],
        response_class=EventSourceResponse,
        responses={200: {"description": "Server-sent events: status, progress, result"}},
    )
    async def run_events(run_id: str, request: Request) -> EventSourceResponse:
        run = find_run(run_id)
        last = request.headers.get("last-event-id", "0")
        after = int(last) if last.isdigit() else 0

        async def stream() -> AsyncIterator[dict[str, str]]:
            async for event in manager.events(run, after):
                yield {"id": str(event.seq), "event": event.kind, "data": json.dumps(event.data)}

        return EventSourceResponse(stream(), ping=15)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    return app
