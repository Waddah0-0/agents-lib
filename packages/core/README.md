# margin-core

The shared core of [margin](https://github.com/Waddah0-0/margin), a library of small AI agents
that answer with evidence. Install it to write your own agent; install an agent (such as
`margin-ai-code-detector`) and `margin-cli` or `margin-api` to use one.

```bash
pip install margin-core
```

## What's in it

- **The agent contract.** An agent is a class with an input model, an output model and an
  async `run` method. `execute()` validates input, times the run, tracks model usage and turns
  any crash into an error result, so callers always get a structured answer.
- **Results with evidence.** Every agent returns an `AgentResult`: a summary, findings, the
  evidence behind each finding, warnings and the agent's own typed data.
- **Discovery.** Agents register under the `margin.agents` entry-point group; installing one is
  enough for every margin tool to find it.
- **Model clients.** One interface for local OpenAI-compatible servers (Ollama, LM Studio,
  llama.cpp, vLLM), Anthropic and OpenAI, with retries, cost tracking and a spending cap. A
  `MockLLM` keeps tests offline.
- **Code loaders.** Local folders and GitHub repositories become a `Workspace`: the files worth
  reading, the ones skipped and why, and the git history. Clones are size-checked and never
  run anything from the repository.

## A minimal agent

```python
from pydantic import BaseModel
from margin_core import AgentInput, AgentResult, BaseAgent, RunContext


class GreetInput(AgentInput):
    name: str


class GreetOutput(BaseModel):
    greeting: str


class Greeter(BaseAgent):
    id = "greeter"
    name = "Greeter"
    description = "Says hello."
    version = "0.1.0"
    InputModel = GreetInput
    OutputModel = GreetOutput

    async def run(self, input: GreetInput, ctx: RunContext) -> AgentResult:
        greeting = f"Hello, {input.name}!"
        return self.make_result(summary=greeting, output=GreetOutput(greeting=greeting))
```

Register it in your package's `pyproject.toml`:

```toml
[project.entry-points."margin.agents"]
greeter = "my_package.agent:Greeter"
```

The full guide is
[docs/writing-an-agent.md](https://github.com/Waddah0-0/margin/blob/main/docs/writing-an-agent.md).

## Settings

Model settings come from environment variables, then settings saved from the web UI, then a
`.env` file, then defaults: `DEFAULT_LLM_PROVIDER` (`local`, `anthropic` or `openai`),
`LOCAL_LLM_BASE_URL`, `LOCAL_LLM_MODEL`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` and
`MAX_COST_USD`. See
[.env.example](https://github.com/Waddah0-0/margin/blob/main/.env.example).

## License

MIT
