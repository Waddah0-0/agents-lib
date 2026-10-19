"""Create a new agent folder that follows the sub-repo standard (PLAN.md §5.11).

Usage::

    uv run python scripts/new_agent.py <agent-id> --name "Readable Name" \\
        --description "One sentence about what it does."
    uv sync --all-packages

It creates ``agents/<agent_id>/`` with a working stub agent (stage ``planned``), and wires
it into the workspace: root ``[tool.uv.sources]``, mypy path and the README agents table.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_agents import ID_RE, ROOT, workspace_config

AGENTS_TABLE_HEADER = "| Agent | What it does | State |"


class ScaffoldError(Exception):
    """The agent cannot be created as requested."""


def class_name_for(agent_id: str) -> str:
    return "".join(part.capitalize() for part in agent_id.split("-")) + "Agent"


def _files(agent_id: str, name: str, description: str, repository: str) -> dict[str, str]:
    package = agent_id.replace("-", "_")
    cls = class_name_for(agent_id)
    folder = f"agents/{package}"
    return {
        "pyproject.toml": f'''[project]
name = "margin-{agent_id}"
version = "0.1.0"
description = "{description}"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "margin-core",
]

[project.entry-points."margin.agents"]
{agent_id} = "{package}.agent:{cls}"

[tool.margin]
id = "{agent_id}"
stage = "planned"
# Turn on mirroring once the agent does real work (and set stage to "experimental"):
# mirror = "<owner>/margin-{agent_id}"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{package}"]
''',
        "README.md": f"""# {name}

{description}

> **Status: planned.** This agent is a scaffold and does not do real work yet.

## What it does

TODO: the problem this agent solves and who it is for.

## How it works

TODO: the steps it takes, in plain words.

## Input

| Field | Default | Meaning |
|---|---|---|
| `target` | required | TODO. The primary input. |

## Output

TODO: what `data` contains and which findings it reports.

## Limits

TODO: what it cannot do, and when not to trust it.

## Usage

```bash
margin run {agent_id} <target>
```

## Development

This agent lives in the [margin]({repository}) monorepo, in
[`{folder}`]({repository}/tree/main/{folder}). If you are reading this in its mirror
repository, that copy is read-only: open issues and pull requests in the main repository.

Run its tests with `uv run pytest {folder}`.
""",
        "CHANGELOG.md": """# Changelog

All notable changes to this agent are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [0.1.0] - Unreleased

### Added
- Initial scaffold.
""",
        f"src/{package}/__init__.py": f'''"""{name}."""

from {package}.agent import {cls}
from {package}.models import {cls}Input, {cls}Output

__version__ = "0.1.0"

__all__ = ["{cls}", "{cls}Input", "{cls}Output", "__version__"]
''',
        f"src/{package}/py.typed": "",
        f"src/{package}/models.py": f'''"""Input and output models of the {name}."""

from __future__ import annotations

from margin_core import AgentInput
from pydantic import BaseModel, Field


class {cls}Input(AgentInput):
    target: str = Field(min_length=1, description="What the agent should analyse.")


class {cls}Output(BaseModel):
    target: str
''',
        f"src/{package}/agent.py": f'''"""{name}: {description}"""

from __future__ import annotations

from margin_core import AgentResult, BaseAgent, RunContext

from {package}.models import {cls}Input, {cls}Output


class {cls}(BaseAgent):
    id = "{agent_id}"
    name = "{name}"
    description = "{description}"
    version = "0.1.0"
    InputModel = {cls}Input
    OutputModel = {cls}Output
    primary_input = "target"

    async def run(self, input: {cls}Input, ctx: RunContext) -> AgentResult:
        ctx.report_progress("start", "Not implemented yet", 0.0)
        return self.make_result(
            summary="This agent is a scaffold and does not do real work yet.",
            output={cls}Output(target=input.target),
            status="partial",
            warnings=["Not implemented yet"],
        )
''',
        "tests/test_agent.py": f"""from {package} import {cls}


async def test_scaffold_runs() -> None:
    result = await {cls}().execute({{"target": "example"}})
    assert result.status == "partial"
    assert result.data == {{"target": "example"}}
""",
    }


def _insert_after_line(text: str, anchor: str, line: str) -> str:
    """Insert ``line`` after the last line of the TOML block or list starting at ``anchor``."""
    lines = text.splitlines(keepends=True)
    start = next(i for i, current in enumerate(lines) if current.startswith(anchor))
    end = start + 1
    while end < len(lines) and lines[end].strip() and not lines[end].startswith("["):
        if lines[end].strip() == "]":
            break
        end += 1
    lines.insert(end, line)
    return "".join(lines)


def _wire_workspace(root: Path, agent_id: str, package: str, name: str, description: str) -> None:
    pyproject = root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    source = f"margin-{agent_id} = {{ workspace = true }}\n"
    if source not in text:
        text = _insert_after_line(text, "[tool.uv.sources]", source)
    mypy_entry = f'    "agents/{package}/src",\n'
    if mypy_entry not in text:
        text = _insert_after_line(text, "mypy_path = [", mypy_entry)
    pyproject.write_text(text, encoding="utf-8")

    readme = root / "README.md"
    lines = readme.read_text(encoding="utf-8").splitlines(keepends=True)
    try:
        header = next(i for i, line in enumerate(lines) if line.startswith(AGENTS_TABLE_HEADER))
    except StopIteration as exc:
        raise ScaffoldError(f"README.md has no agents table ({AGENTS_TABLE_HEADER})") from exc
    end = header + 2
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    row = f"| [{name}](agents/{package}/README.md) | {description} | Planned |\n"
    lines.insert(end, row)
    readme.write_text("".join(lines), encoding="utf-8")


def scaffold(root: Path, agent_id: str, name: str, description: str) -> Path:
    """Create ``agents/<agent_id>/`` under ``root`` and wire it into the workspace."""
    if not ID_RE.match(agent_id):
        raise ScaffoldError(f"Agent id {agent_id!r} must be kebab-case, e.g. 'license-checker'")
    package = agent_id.replace("-", "_")
    if package in sys.stdlib_module_names:
        raise ScaffoldError(f"Package name {package!r} would shadow a standard-library module")
    if '"' in name or '"' in description:
        raise ScaffoldError("Name and description must not contain double quotes")
    agent_dir = root / "agents" / package
    if agent_dir.exists():
        raise ScaffoldError(f"{agent_dir.relative_to(root).as_posix()} already exists")

    repository = workspace_config(root).repository
    for rel, content in _files(agent_id, name, description, repository).items():
        path = agent_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    shutil.copyfile(root / "LICENSE", agent_dir / "LICENSE")
    _wire_workspace(root, agent_id, package, name, description)
    return agent_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a new agent sub-repo.")
    parser.add_argument("agent_id", help="kebab-case id, e.g. license-checker")
    parser.add_argument("--name", required=True, help='readable name, e.g. "License Checker"')
    parser.add_argument("--description", required=True, help="one sentence")
    args = parser.parse_args(argv)
    if not re.match(r".+[.!?]$", args.description):
        args.description += "."
    try:
        agent_dir = scaffold(ROOT, args.agent_id, args.name, args.description)
    except ScaffoldError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rel = agent_dir.relative_to(ROOT).as_posix()
    print(f"Created {rel}. Next:\n  uv sync --all-packages\n  uv run pytest {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
