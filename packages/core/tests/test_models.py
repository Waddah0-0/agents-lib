from datetime import UTC, datetime

import pytest
from agents_core import AgentResult, Evidence, Finding, ProgressEvent, TokenUsage
from pydantic import ValidationError


def test_agent_result_round_trip() -> None:
    result = AgentResult(
        agent_id="x",
        agent_version="1.0",
        status="partial",
        summary="s",
        findings=[Finding(title="t", summary="f", evidence=[Evidence(kind="file", detail="d")])],
        warnings=["w"],
    )
    restored = AgentResult.model_validate_json(result.model_dump_json())
    assert restored == result


def test_models_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Evidence(kind="file", detail="d", bogus=1)  # type: ignore[call-arg]


def test_status_is_constrained() -> None:
    with pytest.raises(ValidationError):
        AgentResult(agent_id="x", agent_version="1", status="weird", summary="s")  # type: ignore[arg-type]


def test_token_usage_arithmetic() -> None:
    a = TokenUsage(llm_calls=1, input_tokens=10, output_tokens=5, cost_usd=0.5)
    b = TokenUsage(llm_calls=2, input_tokens=20, output_tokens=10, cost_usd=1.0)
    assert (a + b).llm_calls == 3
    assert (b - a) == TokenUsage(llm_calls=1, input_tokens=10, output_tokens=5, cost_usd=0.5)


def test_progress_fraction_bounds() -> None:
    assert ProgressEvent(stage="x", fraction=1.0).timestamp <= datetime.now(UTC)
    with pytest.raises(ValidationError):
        ProgressEvent(stage="x", fraction=1.5)
