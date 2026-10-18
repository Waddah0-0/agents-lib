from __future__ import annotations

from typing import ClassVar

import pytest
from agents_core import AgentInput, AgentResult, BaseAgent, InputValidationError, RunContext
from agents_core.inputs import bind_input, parse_assignment
from pydantic import BaseModel


class In(AgentInput):
    target: str
    label: str | None = None
    count: int = 1
    tags: list[str] = []
    strict: bool = False


class Out(BaseModel):
    ok: bool


class WithPrimary(BaseAgent):
    id = "with-primary"
    name = "With primary"
    description = "test"
    version = "0.0.1"
    InputModel = In
    OutputModel = Out
    primary_input: ClassVar[str | None] = "target"

    async def run(self, input: In, ctx: RunContext) -> AgentResult:
        return self.make_result(summary="ok", output=Out(ok=True))


class WithoutPrimary(WithPrimary):
    id = "without-primary"
    primary_input: ClassVar[str | None] = None


def test_positional_fills_primary_field() -> None:
    assert bind_input(WithPrimary, positional="./src") == {"target": "./src"}


def test_assignments_are_typed_by_json_except_strings() -> None:
    data = bind_input(
        WithPrimary,
        positional="x",
        assignments=["count=3", "strict=true", 'tags=["a","b"]', "label=123"],
    )
    assert data == {"target": "x", "count": 3, "strict": True, "tags": ["a", "b"], "label": "123"}
    WithPrimary.parse_input(data)  # validates


def test_assignments_override_base() -> None:
    data = bind_input(WithPrimary, assignments=["count=5"], base={"target": "t", "count": 2})
    assert data == {"target": "t", "count": 5}


def test_value_may_contain_equals_sign() -> None:
    assert parse_assignment(WithPrimary, "label=a=b") == ("label", "a=b")


@pytest.mark.parametrize("bad", ["novalue", "=x", ""])
def test_malformed_assignment(bad: str) -> None:
    with pytest.raises(InputValidationError):
        bind_input(WithPrimary, assignments=[bad])


def test_positional_without_primary_field() -> None:
    with pytest.raises(InputValidationError, match="positional"):
        bind_input(WithoutPrimary, positional="x")


def test_positional_and_assignment_conflict() -> None:
    with pytest.raises(InputValidationError, match="both"):
        bind_input(WithPrimary, positional="a", assignments=["target=b"])


def test_unknown_field_fails_at_validation() -> None:
    data = bind_input(WithPrimary, positional="x", assignments=["nope=1"])
    with pytest.raises(InputValidationError):
        WithPrimary.parse_input(data)
