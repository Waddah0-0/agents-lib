from __future__ import annotations

import pytest
from agents_core.errors import BudgetExceededError, LLMError, TransientLLMError
from agents_core.llm import (
    MockLLM,
    ModelPricing,
    create_llm,
    extract_json,
    lookup_pricing,
)
from agents_core.llm.pricing import CONSERVATIVE_FALLBACK
from pydantic import BaseModel


class SimpleSchema(BaseModel):
    name: str
    count: int


def test_pricing_lookup() -> None:
    anthropic_p = lookup_pricing("anthropic", "claude-sonnet-4-5")
    assert anthropic_p.input_per_mtok == 3.0
    assert anthropic_p.output_per_mtok == 15.0

    openai_p = lookup_pricing("openai", "gpt-4o-mini-2024-07-18")
    assert openai_p.input_per_mtok == 0.15

    unknown_p = lookup_pricing("anthropic", "unknown-weird-model")
    assert unknown_p == CONSERVATIVE_FALLBACK


def test_extract_json_variants() -> None:
    assert extract_json('{"a": 1}') == '{"a": 1}'
    assert extract_json('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert extract_json('Here is your json: {"a": 1} Hope that helps!') == '{"a": 1}'
    assert extract_json("[1, 2, 3]") == "[1, 2, 3]"

    with pytest.raises(ValueError, match="No valid JSON"):
        extract_json("no json here at all")


async def test_mock_llm_queue_and_echo() -> None:
    llm = MockLLM(["first reply", "second reply"])
    r1 = await llm.complete("prompt 1")
    assert r1.text == "first reply"
    r2 = await llm.complete("prompt 2")
    assert r2.text == "second reply"

    # Default fallback echoes the last user message
    r3 = await llm.complete("fallback echo")
    assert r3.text == "fallback echo"
    assert len(llm.calls) == 3


async def test_mock_llm_callable_responder() -> None:
    llm = MockLLM(lambda msgs, sys: f"REPLIED: {msgs[-1].content}")
    res = await llm.complete("testing")
    assert res.text == "REPLIED: testing"


async def test_mock_llm_retries_transient_error() -> None:
    # First attempt raises TransientLLMError, second succeeds
    llm = MockLLM([TransientLLMError("Temporary rate limit"), "recovered"])
    res = await llm.complete("test")
    assert res.text == "recovered"
    assert len(llm.calls) == 2


async def test_mock_llm_exceeds_max_retries() -> None:
    llm = MockLLM([TransientLLMError("fail 1"), TransientLLMError("fail 2")], max_retries=1)
    with pytest.raises(TransientLLMError):
        await llm.complete("test")


async def test_budget_exceeded_error() -> None:
    pricing = ModelPricing(input_per_mtok=1000.0, output_per_mtok=2000.0)
    llm = MockLLM(["ok"], pricing=pricing, max_cost_usd=0.001)
    with pytest.raises(BudgetExceededError):
        await llm.complete("a very long prompt that exceeds the budget limit")


async def test_complete_structured_success() -> None:
    llm = MockLLM(['{"name": "agent", "count": 42}'])
    parsed = await llm.complete_structured(SimpleSchema, "Give me agent data")
    assert parsed.name == "agent"
    assert parsed.count == 42


async def test_complete_structured_repair_attempt() -> None:
    # First response invalid, second response valid after repair feedback
    llm = MockLLM(['{"invalid": "data"}', '{"name": "repaired", "count": 10}'])
    parsed = await llm.complete_structured(SimpleSchema, "Give data")
    assert parsed.name == "repaired"
    assert parsed.count == 10
    assert len(llm.calls) == 2


async def test_complete_structured_fails_after_repairs() -> None:
    llm = MockLLM(["not json", "still not json"])
    with pytest.raises(LLMError, match="failed schema validation"):
        await llm.complete_structured(SimpleSchema, "Give data", max_repair_attempts=1)


def test_create_llm_mock() -> None:
    llm = create_llm(provider="mock")
    assert isinstance(llm, MockLLM)


def test_create_llm_unknown_provider() -> None:
    with pytest.raises(LLMError, match="Unknown LLM provider"):
        create_llm(provider="unknown-provider")
