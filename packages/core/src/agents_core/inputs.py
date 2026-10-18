"""Turn command-line style input into an agent's input mapping.

Shared by the CLI and the API so both bind input the same way:

- the positional value fills the agent's ``primary_input`` field;
- ``key=value`` assignments fill any field. Values are parsed as JSON when they are valid
  JSON (``3``, ``true``, ``["a"]``), except for string fields, which always take the raw text;
- a base mapping (e.g. loaded from a JSON file) supplies defaults that assignments override.

Validation against ``InputModel`` still happens in :meth:`BaseAgent.parse_input`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from agents_core.agent import BaseAgent
from agents_core.errors import InputValidationError


def _wants_raw_string(agent_cls: type[BaseAgent], key: str) -> bool:
    prop = agent_cls.InputModel.model_json_schema().get("properties", {}).get(key, {})
    if prop.get("type") == "string":
        return True
    types = {option.get("type") for option in prop.get("anyOf", [])}
    return bool(types) and types <= {"string", "null"}


def parse_assignment(agent_cls: type[BaseAgent], assignment: str) -> tuple[str, Any]:
    """Parse one ``key=value`` assignment for ``agent_cls``."""
    key, sep, raw = assignment.partition("=")
    key = key.strip()
    if not sep or not key:
        raise InputValidationError(f"Expected key=value, got {assignment!r}")
    if _wants_raw_string(agent_cls, key):
        return key, raw
    try:
        return key, json.loads(raw)
    except json.JSONDecodeError:
        return key, raw


def bind_input(
    agent_cls: type[BaseAgent],
    *,
    positional: str | None = None,
    assignments: Sequence[str] = (),
    base: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the raw input mapping for ``agent_cls`` (not yet validated)."""
    data: dict[str, Any] = dict(base or {})
    assigned: set[str] = set()
    for assignment in assignments:
        key, value = parse_assignment(agent_cls, assignment)
        data[key] = value
        assigned.add(key)

    if positional is not None:
        field = agent_cls.primary_input
        if field is None:
            raise InputValidationError(
                f"Agent {agent_cls.id!r} does not take a positional input; use key=value instead"
            )
        if field in assigned:
            raise InputValidationError(
                f"{field!r} was given both as the positional input and as {field}=..."
            )
        data[field] = positional
    return data
