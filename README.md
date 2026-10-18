# agents-lib

agents-lib is a collection of small AI agents that all work the same way. Each agent does
one job, such as looking at a codebase and estimating how much of it was written with AI
tools. Every agent takes typed input, returns the same kind of structured result, and runs
on shared plumbing for loading code, calling a language model, and writing reports.

The idea is that writing the tenth agent should be much cheaper than writing the first.
The hard, boring parts are solved once in a shared core: cloning repositories safely,
skipping lockfiles and minified bundles, retrying flaky model calls, keeping track of cost,
and rendering results. An agent only has to contain the logic that makes it different.

The project is early. The core library is finished and tested. The first real agent, the
command-line tool, the HTTP API and the web UI are still to come (see [Status](#status)).

## Why build it this way

Most "AI agent" code ends up as a pile of one-off scripts. Each one parses its own input,
prints free-form text, and talks to a model in its own slightly different way. That makes
the scripts hard to reuse, hard to test, and impossible to put behind a single interface.

agents-lib makes three decisions to avoid that:

1. **One contract for every agent.** An agent is a Python class with an input model, an
   output model, and an async `run` method. Anything that can run one agent can run all of
   them.
2. **Structured results, never just text.** Every agent returns an `AgentResult`. It holds
   a short summary, a list of findings, the evidence behind each finding, and the agent's
   own typed data. Because the shape is always the same, one generic report or UI can
   display any agent's output, and a conclusion is always backed by evidence you can check.
3. **Agents are plugins.** Each agent is its own installable package. It announces itself
   through a Python entry point, so installing it is enough for the CLI, the API and the
   Python helpers to find it. Adding an agent never means editing the core.

## How it fits together

```
        CLI            HTTP API          Python code
          \               |                  /
           +-------- agent registry --------+
                          |
                     agent.run(input)
                          |
         +----------------+----------------+
         |                |                |
      loaders         LLM client       reporting
  (GitHub, local)  (local, hosted,   (JSON, Markdown)
                       mock)
```

The repository is a single [uv](https://github.com/astral-sh/uv) workspace. Each package
inside it can be versioned and published on its own:

| Path | What it is |
|---|---|
| `packages/core` | The shared foundation: the agent contract, result models, registry, loaders, LLM clients and reporting. |
| `packages/cli` | The `agents` command-line tool (placeholder for now). |
| `packages/api` | The FastAPI server for running agents over HTTP (placeholder for now). |
| `agents/echo` | A minimal reference agent, used for smoke tests and as a template. |
| `agents/ai_code_detector` | The first real agent (in progress). |
| `examples/` | Small runnable scripts. |
| `scripts/` | Workspace tools: create an agent, check agent folders, mirror agents, type-check. |
| `tests/` | Tests for the workspace tools. |
| `docs/` | Guides, starting with [writing an agent](docs/writing-an-agent.md). |

### The core, piece by piece

**The agent contract.** An agent subclasses `BaseAgent`, declares its `InputModel` and
`OutputModel` (Pydantic models), and implements `async def run(input, ctx)`. Callers use
`execute()`, which validates the input, times the run, records model usage, and turns any
crash into an error result. A caller always gets a structured answer back, even when the
agent fails.

**The run context.** Every run receives a `RunContext`. It gives the agent the LLM client,
a progress callback (the CLI can show it as a progress bar, and the API can stream it to a
browser), a cancellation flag, and a logger.

**Loaders.** Agents that work on code never deal with where it came from. A loader turns a
GitHub URL or a local path into a `Workspace`: the files worth analysing, the files that
were skipped and why, and access to the git history. The GitHub loader is deliberately
careful:

- it only accepts `https://github.com/<owner>/<repo>`;
- it skips submodules and treats symlinks as plain files;
- it never prompts for credentials, and enforces size and time limits;
- it never executes anything from the repository.

Filters drop lockfiles, dependency folders, build output, minified bundles, binaries and
generated code before an agent ever sees them.

**LLM clients.** All model access goes through one `LLMClient` interface with two calls:
`complete()` for text and `complete_structured()` for replies that must match a Pydantic
schema. Retries, timeouts, token counting, cost estimates and a hard spending cap are
handled for every provider. A `MockLLM` returns scripted answers, so the test suite never
touches the network.

**Reporting.** Any result can be rendered as JSON or as a readable Markdown report.

## Local models by default

Agents run against a model on your own machine unless you say otherwise, so using them
costs nothing. The default is [Ollama](https://ollama.com) with `qwen2.5:7b`, a model
that runs comfortably on an 8 GB GPU. Any server that speaks the OpenAI chat API works:

| Server | `LOCAL_LLM_BASE_URL` |
|---|---|
| Ollama (default) | `http://localhost:11434` |
| LM Studio | `http://localhost:1234` |
| llama.cpp `llama-server` | `http://localhost:8080` |
| vLLM | `http://localhost:8000` |

When an agent asks for structured output, the schema is passed to the server so the model
is forced to produce valid JSON. Small local models need this to be reliable.

Local models have limits you should know about. They are slower, especially on the first
call while the model loads. They have smaller context windows; for long inputs, start Ollama
with a larger one, for example `OLLAMA_CONTEXT_LENGTH=8192`. And their judgment is weaker
than that of the large hosted models. Anthropic and OpenAI remain available for when that
matters: set `DEFAULT_LLM_PROVIDER` to `anthropic` or `openai` and add the matching API key.

## Agents

Click an agent's name for what it does, how to use it, and its limits.

| Agent | What it does | State |
|---|---|---|
| [AI Code Detector](agents/ai_code_detector/README.md) | Estimates how likely a codebase was written with AI assistance, and shows the evidence. | In progress |
| [Echo](agents/echo/README.md) | Echoes its input back. A reference agent for testing and for copying when you write a new one. | Ready |

## Status

The project is built in phases, each one usable before the next begins.

| Phase | Scope | State |
|---|---|---|
| 0 | Repository skeleton, tooling, CI | Done |
| 1 | Core: contract, models, registry, loaders, LLM clients, reporting | Done |
| 1.5 | Core fixes (per-run LLM budgets, git history scoped to the target, safer clones) and the agent sub-repo standard | Done |
| 2 | Command-line tool (`agents list`, `agents info`, `agents run`) | Next |
| 3 | AI Code Detector with heuristic signals, plus the evaluation harness that measures it | Planned |
| 4 | LLM judge, larger evaluation dataset, calibrated scoring | Planned |
| 5 | HTTP API with background runs and live progress | Planned |
| 6–7 | Web UI: a generic one for every agent, plus a custom view for the detector | Planned |
| 8 | Hardening and the first PyPI release | Planned |

## Getting started

You need Python 3.11 or newer, [uv](https://github.com/astral-sh/uv), and git. To use a
local model you also need Ollama or another server from the table above.

```bash
git clone https://github.com/Waddah0-0/agents-lib.git
cd agents-lib
uv sync --all-packages
cp .env.example .env        # optional; the defaults work with a local Ollama
ollama pull qwen2.5:7b      # only needed for agents that call a model
```

Until the CLI lands, you run agents from Python. This runs the reference echo agent through
the registry:

```python
import asyncio
from agents_core import run_agent


async def main() -> None:
    result = await run_agent("echo", {"message": "hello", "repeat": 2})
    print(result.summary)  # Echoed 11 characters (2x).
    print(result.data)  # {'echoed': 'hello hello', 'length': 11, 'llm_reply': None}


asyncio.run(main())
```

For a complete example (a custom agent with progress reporting and a Markdown report),
run `uv run python examples/custom_agent.py`.

## Writing your own agent

An agent is a folder under `agents/` with its own `pyproject.toml`, a class that
subclasses `BaseAgent`, an entry point that registers it, and tests that use `MockLLM`.
It may import only from `agents_core`, never from another agent. If a new agent seems to
need a change to the core, that change should be general enough to help every agent.

[docs/writing-an-agent.md](docs/writing-an-agent.md) walks through it step by step.

## Development

Run these before you commit. CI runs the same checks on Python 3.11 and 3.12.

```bash
uv run ruff check .          # lint
uv run ruff format --check . # formatting
uv run python scripts/typecheck.py  # strict type checking, per package
uv run pytest                # tests; no network access needed
```

Commits follow the [Conventional Commits](https://www.conventionalcommits.org) style
(`feat:`, `fix:`, `docs:` and so on). Secrets belong in `.env`, which is never committed.

## License

[MIT](LICENSE)
