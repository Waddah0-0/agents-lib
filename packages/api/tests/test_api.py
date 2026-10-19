"""The HTTP API: routes, background runs, events (SSE), cancellation, queues and limits."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Iterator
from importlib.metadata import EntryPoint
from typing import Any, ClassVar

import pytest
from agents_api.app import create_app
from agents_api.settings import ApiSettings
from agents_core import AgentInput, AgentRegistry, AgentResult, BaseAgent, RunContext
from agents_core.registry import ENTRY_POINT_GROUP
from echo_agent import EchoAgent
from fastapi.testclient import TestClient
from pydantic import BaseModel


class SlowInput(AgentInput):
    steps: int = 200
    fail: bool = False


class SlowOutput(BaseModel):
    steps: int


class Slow(BaseAgent):
    id = "slow"
    name = "Slow"
    description = "Counts slowly, checking for cancellation."
    version = "0.0.1"
    InputModel = SlowInput
    OutputModel = SlowOutput
    honours_cancel: ClassVar[bool] = True

    async def run(self, input: SlowInput, ctx: RunContext) -> AgentResult:
        if input.fail:
            raise RuntimeError("boom")
        for i in range(input.steps):
            if self.honours_cancel:
                ctx.check_cancelled()
            ctx.report_progress("count", f"step {i}", i / input.steps)
            await asyncio.sleep(0.01)
        return self.make_result(summary="counted", output=SlowOutput(steps=input.steps))


class Stubborn(Slow):
    id = "stubborn"
    honours_cancel = False


class Gpu(Slow):
    id = "gpu"
    uses_llm = True


def _registry() -> AgentRegistry:
    broken = EntryPoint(name="broken", value="no_such_module:Agent", group=ENTRY_POINT_GROUP)
    registry = AgentRegistry([broken])
    for agent in (EchoAgent, Slow, Stubborn, Gpu):
        registry.register(agent)
    return registry


def make_client(**overrides: Any) -> TestClient:
    settings = ApiSettings(**{"cancel_grace_s": 0.3, "max_body_bytes": 2000, **overrides})
    app = create_app(registry=_registry(), settings=settings, llm_factory=lambda: None)
    return TestClient(app)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with make_client() as c:
        yield c


def wait_for(client: TestClient, run_id: str, statuses: set[str], timeout: float = 10) -> dict:  # type: ignore[type-arg]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/runs/{run_id}").json()
        if body["status"] in statuses:
            return body  # type: ignore[no-any-return]
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} never reached {statuses}: {body['status']}")


def start(client: TestClient, agent: str, body: dict[str, Any]) -> str:
    response = client.post(f"/agents/{agent}/runs", json=body)
    assert response.status_code == 202, response.text
    return response.json()["run_id"]  # type: ignore[no-any-return]


def sse(client: TestClient, run_id: str, last_id: str | None = None) -> list[dict[str, Any]]:
    headers = {"Last-Event-ID": last_id} if last_id else {}
    events: list[dict[str, str]] = []
    current: dict[str, str] = {}
    with client.stream("GET", f"/runs/{run_id}/events", headers=headers) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        for line in response.iter_lines():
            if not line:
                if current:
                    events.append(current)
                current = {}
            elif ":" in line and not line.startswith(":"):
                key, value = line.split(":", 1)
                current[key] = value.strip()
    return [
        {"id": int(e["id"]), "event": e["event"], "data": json.loads(e["data"])} for e in events
    ]


# ---- agents -----------------------------------------------------------------------------


def test_health(client: TestClient) -> None:
    assert client.get("/health").json()["status"] == "ok"


def test_list_and_describe_agents(client: TestClient) -> None:
    body = client.get("/agents").json()
    assert [a["id"] for a in body["agents"]] == ["echo", "gpu", "slow", "stubborn"]
    assert "broken" in body["load_errors"]
    echo = client.get("/agents/echo").json()
    assert echo["primary_input"] == "message" and echo["uses_llm"] is False
    assert echo["input_schema"]["required"] == ["message"]
    assert client.get("/agents/nope").status_code == 404
    broken = client.get("/agents/broken")
    assert broken.status_code == 500 and "failed to load" in broken.json()["detail"]


# ---- runs -------------------------------------------------------------------------------


def test_run_echo_end_to_end(client: TestClient) -> None:
    response = client.post("/agents/echo/runs", json={"message": "hi", "repeat": 2})
    assert response.status_code == 202
    created = response.json()
    assert created["links"]["events"] == f"/runs/{created['run_id']}/events"
    done = wait_for(client, created["run_id"], {"done"})
    assert done["result"]["status"] == "ok"
    assert done["result"]["data"]["echoed"] == "hi hi"
    assert done["finished_at"] is not None and done["queue_position"] is None
    assert any(r["run_id"] == created["run_id"] for r in client.get("/runs").json())


def test_bad_requests(client: TestClient) -> None:
    invalid = client.post("/agents/echo/runs", json={"message": "", "repeat": 99})
    assert invalid.status_code == 422 and "Invalid input" in invalid.json()["detail"]
    assert client.post("/agents/echo/runs", json={"message": "x", "nope": 1}).status_code == 422
    assert client.post("/agents/nope/runs", json={}).status_code == 404
    assert client.get("/runs/doesnotexist").status_code == 404


def test_agent_failure_is_a_result_not_an_http_error(client: TestClient) -> None:
    run_id = start(client, "slow", {"fail": True})
    done = wait_for(client, run_id, {"done"})
    assert done["result"]["status"] == "error"
    assert "RuntimeError: boom" in done["result"]["error"]


# ---- events -----------------------------------------------------------------------------


def test_events_replay_history_then_end_with_the_result(client: TestClient) -> None:
    run_id = start(client, "slow", {"steps": 5})
    wait_for(client, run_id, {"done"})
    events = sse(client, run_id)  # connects after the run finished: full history
    kinds = [e["event"] for e in events]
    assert kinds[0] == "status" and events[0]["data"] == {"status": "queued"}
    assert kinds.count("progress") == 5 and kinds[-1] == "result"
    assert [e["id"] for e in events] == sorted(e["id"] for e in events)
    assert events[-1]["data"]["result"]["data"] == {"steps": 5}

    resumed = sse(client, run_id, last_id=str(events[3]["id"]))
    assert [e["id"] for e in resumed] == [e["id"] for e in events[4:]]


def test_events_stream_live(client: TestClient) -> None:
    run_id = start(client, "slow", {"steps": 30})
    events = sse(client, run_id)  # connects while queued or running
    assert events[-1]["event"] == "result"
    assert sum(e["event"] == "progress" for e in events) == 30


# ---- cancellation and queues ------------------------------------------------------------


def test_cancel_a_running_run(client: TestClient) -> None:
    run_id = start(client, "slow", {"steps": 2000})
    wait_for(client, run_id, {"running"})
    assert client.delete(f"/runs/{run_id}").status_code == 202
    done = wait_for(client, run_id, {"cancelled"})
    assert done["result"]["error"] == "Run was cancelled"
    assert client.delete(f"/runs/{run_id}").json()["status"] == "cancelled"  # idempotent


def test_a_run_that_ignores_cancellation_is_stopped_after_the_grace_period(
    client: TestClient,
) -> None:
    run_id = start(client, "stubborn", {"steps": 2000})
    wait_for(client, run_id, {"running"})
    client.delete(f"/runs/{run_id}")
    done = wait_for(client, run_id, {"cancelled"}, timeout=5)
    assert done["result"] is None  # the task was stopped before the agent returned


def test_llm_runs_queue_one_at_a_time() -> None:
    with make_client(llm_concurrency=1) as client:
        first = start(client, "gpu", {"steps": 2000})
        second = start(client, "gpu", {"steps": 5})
        wait_for(client, first, {"running"})
        queued = client.get(f"/runs/{second}").json()
        assert queued["status"] == "queued" and queued["queue_position"] == 1
        other = start(client, "slow", {"steps": 5})  # other pool: not blocked by the GPU
        assert wait_for(client, other, {"done"})["result"]["status"] == "ok"

        assert client.delete(f"/runs/{second}").json()["status"] == "cancelled"  # while queued
        client.delete(f"/runs/{first}")
        wait_for(client, first, {"cancelled"})


# ---- limits and housekeeping ------------------------------------------------------------


def test_request_body_limit(client: TestClient) -> None:
    big = {"message": "x" * 5000}
    response = client.post("/agents/echo/runs", json=big)
    assert response.status_code == 413
    chunked = client.post(
        "/agents/echo/runs",
        content=iter([json.dumps(big).encode()]),
        headers={"content-type": "application/json"},
    )
    assert chunked.status_code == 413


def test_cors_allows_configured_origins_only(client: TestClient) -> None:
    allowed = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    denied = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in denied.headers


def test_finished_runs_expire() -> None:
    with make_client(result_ttl_s=0.0) as client:
        run_id = start(client, "echo", {"message": "hi"})
        wait_for(client, run_id, {"done"})
        deadline = time.monotonic() + 5  # the sweeper runs at most once a second
        while client.get(f"/runs/{run_id}").status_code != 404:
            assert time.monotonic() < deadline, "finished run was never removed"
            time.sleep(0.1)


def test_api_works_when_no_model_can_be_created() -> None:
    def broken_factory() -> None:
        raise RuntimeError("no API key")

    settings = ApiSettings()
    app = create_app(registry=_registry(), settings=settings, llm_factory=broken_factory)
    with TestClient(app) as client:
        run_id = start(client, "echo", {"message": "hi"})
        assert wait_for(client, run_id, {"done"})["result"]["status"] == "ok"
