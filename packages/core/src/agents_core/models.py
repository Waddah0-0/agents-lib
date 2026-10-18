"""Standard Pydantic models shared by every agent.

A generic UI can render ``summary``, ``findings`` and ``evidence`` of any
:class:`AgentResult` without knowing anything about the agent that produced it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ResultStatus = Literal["ok", "partial", "error"]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(_StrictModel):
    """A single, checkable piece of evidence supporting a finding."""

    kind: str = Field(description='Evidence type, e.g. "file", "commit", "config", "metric".')
    location: str | None = Field(
        default=None, description='Where to look, e.g. "src/utils.py:10-42" or a commit SHA.'
    )
    detail: str = Field(description="Human-readable explanation.")
    weight: float | None = Field(
        default=None, description="Contribution to the score, if applicable."
    )


class Finding(_StrictModel):
    """A titled conclusion backed by evidence."""

    title: str
    severity_or_score: float | None = None
    summary: str
    evidence: list[Evidence] = Field(default_factory=list)


class TokenUsage(_StrictModel):
    """Aggregated LLM usage and estimated cost."""

    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            llm_calls=self.llm_calls + other.llm_calls,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cost_usd=self.cost_usd + other.cost_usd,
        )

    def __sub__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            llm_calls=self.llm_calls - other.llm_calls,
            input_tokens=self.input_tokens - other.input_tokens,
            output_tokens=self.output_tokens - other.output_tokens,
            cost_usd=max(0.0, self.cost_usd - other.cost_usd),
        )


class RunMetadata(_StrictModel):
    """Execution metadata attached to every result."""

    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_s: float | None = None
    model: str | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)
    extra: dict[str, Any] = Field(default_factory=dict)


class AgentInput(_StrictModel):
    """Base class for agent input models. Unknown fields are rejected."""


class AgentResult(_StrictModel):
    """The standard result returned by every agent.

    ``status`` semantics:

    - ``ok``: everything requested was done. ``error`` is null.
    - ``partial``: a usable result, but some requested work was skipped (a budget or time cap
      was hit, some files were unreadable, an optional step was unavailable). Each skipped
      part has an entry in ``warnings``. ``data`` is complete in shape but may hold fewer
      items. ``error`` is null.
    - ``error``: no usable result. ``data`` is empty and ``error`` holds the message.
    """

    agent_id: str
    agent_version: str
    status: ResultStatus
    summary: str = Field(description="2-3 sentence human summary.")
    data: dict[str, Any] = Field(
        default_factory=dict, description="Agent-specific payload, validated by its OutputModel."
    )
    findings: list[Finding] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = Field(default=None, description="Error message when status is 'error'.")
    metadata: RunMetadata = Field(default_factory=RunMetadata)


class ProgressEvent(_StrictModel):
    """A progress update emitted during a run (consumed by CLI/UI)."""

    stage: str
    message: str = ""
    fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentInfo(_StrictModel):
    """Static description of an agent, including its JSON schemas."""

    id: str
    name: str
    description: str
    version: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    primary_input: str | None = Field(
        default=None, description="Input field filled by a positional CLI argument."
    )
