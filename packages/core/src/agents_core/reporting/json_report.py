"""Render an :class:`AgentResult` as JSON."""

from __future__ import annotations

from pathlib import Path

from agents_core.models import AgentResult


def to_json(result: AgentResult, *, indent: int | None = 2) -> str:
    return result.model_dump_json(indent=indent)


def write_json(result: AgentResult, path: str | Path, *, indent: int | None = 2) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_json(result, indent=indent) + "\n", encoding="utf-8")
    return out
