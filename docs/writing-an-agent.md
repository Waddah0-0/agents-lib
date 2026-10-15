# Writing an Agent

This guide walks you through building and publishing a new agent in `agents-lib`.

---

## 1. The Agent Architecture

Every agent in `agents-lib` is an isolated package located in the `agents/` directory that adheres to the **Agent Contract**.

Key principles:
- **Shared Foundation:** All agents import solely from `agents_core`.
- **Strict Typing:** Input and Output models are Pydantic schemas. Loose dictionaries across agent boundaries are disallowed.
- **Async Execution:** The main entrypoint `async def run(self, input, ctx: RunContext)` is non-blocking.
- **Verifiable Evidence:** Findings must link to structured `Evidence` objects (`file`, `commit`, `config`, or `metric`).
- **Entry-Point Discovery:** Agents register via Python entry points in `pyproject.toml` and are discovered dynamically without modifying the CLI or API.

---

## 2. Directory Layout

Create a new directory in `agents/<your_agent_name>`:

```text
agents/my_agent/
├── pyproject.toml
├── README.md
├── src/
│   └── my_agent/
│       ├── __init__.py
│       ├── py.typed
│       └── agent.py
└── tests/
    └── test_agent.py
```

---

## 3. Package Configuration (`pyproject.toml`)

Configure your package with `agents-lib-core` as a workspace dependency and register the agent entry point:

```toml
[project]
name = "agents-lib-my-agent"
version = "0.1.0"
description = "My custom AI agent"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "agents-lib-core",
]

[project.entry-points."agents_lib.agents"]
my-agent = "my_agent.agent:MyAgent"

[tool.uv.sources]
agents-lib-core = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/my_agent"]
```

---

## 4. Implementing the Agent (`src/my_agent/agent.py`)

Subclass `BaseAgent` and implement the `run` method:

```python
from __future__ import annotations
from pydantic import BaseModel, Field
from agents_core import (
    BaseAgent,
    AgentInput,
    AgentResult,
    RunContext,
    Finding,
    Evidence,
)


class MyAgentInput(AgentInput):
    target: str = Field(description="Repository or file to analyze.")
    threshold: float = Field(default=0.8, ge=0.0, le=1.0)


class MyAgentOutput(BaseModel):
    score: float
    items_inspected: int


class MyAgent(BaseAgent):
    id = "my-agent"
    name = "My Custom Agent"
    description = "Inspects targets and provides structured evidence."
    version = "0.1.0"
    InputModel = MyAgentInput
    OutputModel = MyAgentOutput

    async def run(self, input: MyAgentInput, ctx: RunContext) -> AgentResult:
        # 1. Emit progress updates
        ctx.report_progress("scan", "Scanning files...", fraction=0.2)

        # 2. Check cooperative cancellation token
        ctx.check_cancelled()

        # 3. Optional: interact with LLM via RunContext
        if ctx.llm:
            response = await ctx.llm.complete("Analyze this summary")

        # 4. Construct findings & evidence
        findings = [
            Finding(
                title="Threshold Exceeded",
                severity_or_score=0.9,
                summary="Target exceeds configured threshold.",
                evidence=[
                    Evidence(
                        kind="metric",
                        location="target.py:42",
                        detail="Score calculated at 0.90",
                        weight=0.9,
                    )
                ],
            )
        ]

        ctx.report_progress("done", "Complete", fraction=1.0)

        # 5. Return validated AgentResult
        return self.make_result(
            summary="Completed inspection successfully.",
            output=MyAgentOutput(score=0.9, items_inspected=1),
            findings=findings,
        )
```

---

## 5. Testing Your Agent

Write unit tests that mock LLM calls using `MockLLM` to guarantee fast, deterministic tests without network reliance:

```python
import pytest
from agents_core import run_agent, RunContext
from agents_core.llm import MockLLM


async def test_my_agent_runs() -> None:
    llm = MockLLM(["Simulated answer"])
    result = await run_agent(
        "my-agent",
        {"target": "dummy/path", "threshold": 0.5},
        llm=llm,
    )
    assert result.status == "ok"
    assert result.data["score"] == 0.9
```

---

## 6. Running Your Agent

### From Python:
```python
import asyncio
from agents_core import run_agent


async def main():
    result = await run_agent("my-agent", {"target": "src/"})
    print(result.summary)


asyncio.run(main())
```

### From CLI:
```bash
uv run agents run my-agent src/ --format markdown
```
