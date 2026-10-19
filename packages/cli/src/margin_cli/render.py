"""Turn agent metadata into readable terminal output."""

from __future__ import annotations

import json
from typing import Any

from margin_core import AgentInfo
from rich.table import Table


def schema_type(prop: dict[str, Any]) -> str:
    """A short, readable type for one JSON-schema property."""
    if "enum" in prop:
        return " | ".join(json.dumps(v) for v in prop["enum"])
    if "$ref" in prop:
        return str(prop["$ref"]).rsplit("/", 1)[-1]
    if "anyOf" in prop:
        return " | ".join(schema_type(option) for option in prop["anyOf"])
    kind = prop.get("type")
    if kind == "array":
        return f"list[{schema_type(prop.get('items', {}))}]"
    if kind == "object":
        return "object"
    return {"string": "text", "integer": "integer", "number": "number", "boolean": "true/false",
            "null": "null"}.get(str(kind), str(kind or "any"))  # fmt: skip


def input_fields(info: AgentInfo) -> list[dict[str, str]]:
    """One row per input field: name, type, requirement/default and description."""
    schema = info.input_schema
    required = set(schema.get("required", []))
    rows = []
    for name, prop in schema.get("properties", {}).items():
        if name in required:
            default = "required"
        elif "default" in prop:
            default = json.dumps(prop["default"])
        else:
            default = "optional"
        rows.append(
            {
                "name": name,
                "type": schema_type(prop),
                "default": default,
                "description": str(prop.get("description", "")),
                "primary": "yes" if name == info.primary_input else "",
            }
        )
    rows.sort(key=lambda row: (row["primary"] != "yes", row["default"] != "required"))
    return rows


def agents_table(infos: list[AgentInfo]) -> Table:
    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Version", no_wrap=True)
    table.add_column("Description")
    for info in infos:
        table.add_row(info.id, info.name, info.version, info.description)
    return table


def fields_table(info: AgentInfo) -> Table:
    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Type")
    table.add_column("Default")
    table.add_column("Description")
    for row in input_fields(info):
        name = row["name"] + (" (positional)" if row["primary"] else "")
        table.add_row(name, row["type"], row["default"], row["description"])
    return table
