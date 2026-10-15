import pytest
from agents_core import (
    AgentInput,
    AgentResult,
    BaseAgent,
    CancellationToken,
    InputValidationError,
    ProgressEvent,
    RunContext,
)
from agents_core.llm import MockLLM
from pydantic import BaseModel, ValidationError


class In(AgentInput):
    n: int


class Out(BaseModel):
    doubled: int


class Doubler(BaseAgent):
    id = "doubler"
    name = "Doubler"
    description = "Doubles a number"
    version = "1.2.3"
    InputModel = In
    OutputModel = Out

    async def run(self, input: In, ctx: RunContext) -> AgentResult:
        ctx.report_progress("work", fraction=0.5)
        if input.n < 0:
            raise ValueError("negative")
        if input.n == 42 and ctx.llm is not None:
            await ctx.llm.complete("hi")
        return self.make_result(summary="done", output=Out(doubled=input.n * 2))


class BadOutput(Doubler):
    async def run(self, input: In, ctx: RunContext) -> AgentResult:
        return self.make_result(summary="bad", output=In(n=1))


def test_info_exposes_schemas() -> None:
    info = Doubler.info()
    assert info.id == "doubler"
    assert info.input_schema["properties"]["n"]["type"] == "integer"
    assert "doubled" in info.output_schema["properties"]


async def test_execute_success_fills_metadata() -> None:
    events: list[ProgressEvent] = []
    result = await Doubler().execute({"n": 4}, RunContext(progress=events.append))
    assert result.status == "ok"
    assert result.data == {"doubled": 8}
    assert result.agent_version == "1.2.3"
    assert result.metadata.started_at is not None
    assert result.metadata.duration_s is not None
    assert events[0].stage == "work"


async def test_execute_accepts_model_input() -> None:
    result = await Doubler().execute(In(n=1))
    assert result.data["doubled"] == 2


async def test_invalid_input_raises() -> None:
    with pytest.raises(InputValidationError):
        await Doubler().execute({"n": "nope"})
    with pytest.raises(InputValidationError):
        await Doubler().execute({"n": 1, "extra": True})


async def test_exception_becomes_error_result() -> None:
    result = await Doubler().execute({"n": -1})
    assert result.status == "error"
    assert result.error == "ValueError: negative"


async def test_cancelled_before_start() -> None:
    token = CancellationToken()
    token.cancel()
    result = await Doubler().execute({"n": 1}, RunContext(cancel_token=token))
    assert result.status == "error"
    assert result.error == "Run was cancelled"


async def test_usage_is_per_run_delta() -> None:
    llm = MockLLM()
    agent = Doubler(llm=llm)
    first = await agent.execute({"n": 42})
    second = await agent.execute({"n": 42})
    assert first.metadata.usage.llm_calls == 1
    assert second.metadata.usage.llm_calls == 1
    assert llm.usage.llm_calls == 2


async def test_make_result_validates_output() -> None:
    result = await BadOutput().execute({"n": 1})
    assert result.status == "error"
    assert result.error is not None and "ValidationError" in result.error


def test_output_validation_error_type() -> None:
    with pytest.raises(ValidationError):
        Doubler().make_result(summary="x", output=In(n=1))
