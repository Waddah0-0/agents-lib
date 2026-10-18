"""Per-run LLM sessions: separate usage, budgets and warnings over one shared client."""

from __future__ import annotations

import asyncio

import pytest
from agents_core import AgentInput, AgentResult, BaseAgent, RunContext
from agents_core.errors import BudgetExceededError
from agents_core.llm import LLMResponse, LLMSession, Message, MockLLM, ModelPricing
from pydantic import BaseModel

PRICEY = ModelPricing(input_per_mtok=1_000_000.0, output_per_mtok=0.0)  # $1 per input token


async def test_session_tracks_its_own_usage_and_feeds_the_client() -> None:
    client = MockLLM(["a", "b", "c"])
    first, second = client.session(), client.session()
    await first.complete("one")
    await second.complete("two")
    await second.complete("three")
    assert first.usage.llm_calls == 1
    assert second.usage.llm_calls == 2
    assert client.usage.llm_calls == 3
    assert isinstance(first, LLMSession) and first.client is client
    assert first.model == client.model


async def test_session_budget_is_independent_per_run() -> None:
    client = MockLLM(pricing=PRICEY)
    session = client.session(max_cost_usd=10.0)
    await session.complete("x" * 4)  # about 2 tokens -> about $2
    with pytest.raises(BudgetExceededError):
        await session.complete("x" * 40)
    other = client.session(max_cost_usd=10.0)
    await other.complete("x" * 4)  # a fresh run is not blocked by the first one's spending


async def test_client_budget_still_applies_through_sessions() -> None:
    client = MockLLM(pricing=PRICEY, max_cost_usd=2.5)  # each call: est. $2, actual $1
    session = client.session()
    await session.complete("x" * 4)
    with pytest.raises(BudgetExceededError):
        await client.session().complete("x" * 4)


async def test_session_collects_provider_warnings() -> None:
    class WarningLLM(MockLLM):
        async def _complete_raw(
            self, messages: list[Message], *args: object, **kw: object
        ) -> LLMResponse:
            response = await super()._complete_raw(messages, *args, **kw)  # type: ignore[arg-type]
            return response.model_copy(update={"warnings": ["truncated"]})

    client = WarningLLM()
    session = client.session()
    await session.complete("a")
    await session.complete("b")
    assert session.warnings == ["truncated"]
    assert client.warnings == ["truncated"]


class In(AgentInput):
    calls: int


class Out(BaseModel):
    calls: int


class Caller(BaseAgent):
    id = "caller"
    name = "Caller"
    description = "Calls the LLM n times"
    version = "0.0.1"
    InputModel = In
    OutputModel = Out

    async def run(self, input: In, ctx: RunContext) -> AgentResult:
        llm = ctx.require_llm()
        for _ in range(input.calls):
            await llm.complete("hi")
            await asyncio.sleep(0)  # let concurrent runs interleave
        return self.make_result(summary="ok", output=Out(calls=input.calls))


async def test_concurrent_runs_on_shared_client_report_own_usage() -> None:
    client = MockLLM()
    agent = Caller(llm=client)
    a, b = await asyncio.gather(agent.execute({"calls": 2}), agent.execute({"calls": 5}))
    assert a.metadata.usage.llm_calls == 2
    assert b.metadata.usage.llm_calls == 5
    assert client.usage.llm_calls == 7


async def test_run_budget_comes_from_context() -> None:
    client = MockLLM(pricing=PRICEY)
    result = await Caller(llm=client).execute({"calls": 3}, RunContext(max_cost_usd=1.0))
    assert result.status == "error"
    assert result.error is not None and "BudgetExceededError" in result.error
