"""End-to-end: the echo agent is discovered through its real entry point and runs."""

import pytest
from agents_core import (
    AgentRegistry,
    InputValidationError,
    ProgressEvent,
    RunContext,
    get_agent,
    list_agents,
    run_agent,
)
from agents_core.llm import MockLLM
from agents_core.reporting import to_json, to_markdown
from echo_agent import EchoAgent


def test_echo_is_discovered_via_entry_point() -> None:
    assert get_agent("echo") is EchoAgent
    ids = [info.id for info in list_agents()]
    assert "echo" in ids


async def test_run_echo_through_registry() -> None:
    events: list[ProgressEvent] = []
    result = await run_agent(
        "echo",
        {"message": "hi", "repeat": 3},
        ctx=RunContext(progress=events.append),
        registry=AgentRegistry(),
    )
    assert result.status == "ok"
    assert result.data == {"echoed": "hi hi hi", "length": 8, "llm_reply": None}
    assert result.metadata.duration_s is not None
    assert [e.stage for e in events] == ["echo", "done"]
    assert '"echoed": "hi hi hi"' in to_json(result)
    assert "# echo report" in to_markdown(result)


async def test_echo_with_mock_llm_records_usage() -> None:
    llm = MockLLM(["pong"])
    result = await run_agent("echo", {"message": "ping", "use_llm": True}, llm=llm)
    assert result.status == "ok"
    assert result.data["llm_reply"] == "pong"
    assert result.metadata.model == "mock-model"
    assert result.metadata.usage.llm_calls == 1


async def test_echo_without_llm_returns_error_result() -> None:
    result = await run_agent("echo", {"message": "ping", "use_llm": True})
    assert result.status == "error"
    assert result.error is not None and "LLM" in result.error


async def test_echo_rejects_invalid_input() -> None:
    with pytest.raises(InputValidationError):
        await run_agent("echo", {"message": "", "repeat": 99})
