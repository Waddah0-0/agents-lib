# Echo

The smallest complete agent. It exists to test the toolchain and to show what an agent
looks like.

## What it does

Echoes a message back, optionally repeated, and can also ask the configured model to reply
to it. It touches no files and no network unless `use_llm` is on.

Use it to smoke-test the registry, the CLI, the API or the UI, and as a reference when you
write a new agent (see [writing an agent](https://github.com/Waddah0-0/agents-lib/blob/main/docs/writing-an-agent.md)).

## How it works

1. Validates the input.
2. Joins `repeat` copies of `message` with spaces.
3. If `use_llm` is true, sends `message` to the model and keeps the reply.
4. Returns the echo as `data` and as one finding with a length metric as evidence.

It reports progress at each step and checks for cancellation before calling the model.

## Input

| Field | Type | Default | Meaning |
|---|---|---|---|
| `message` | text, required | | The text to echo. This is the agent's primary input. |
| `repeat` | 1 to 10 | 1 | How many times to repeat it. |
| `use_llm` | true/false | false | Also send the message to the model and include its reply. |

## Output

| Field | Meaning |
|---|---|
| `echoed` | The repeated message. |
| `length` | Its length in characters. |
| `llm_reply` | The model's reply, or null when `use_llm` is off. |

## Limits

None worth noting: it does no analysis. With `use_llm` on, it needs a reachable model
(by default a local Ollama server).

## Usage

```python
import asyncio

from agents_core import run_agent


async def main() -> None:
    result = await run_agent("echo", {"message": "hello", "repeat": 2})
    print(result.data["echoed"])  # hello hello


asyncio.run(main())
```

## Development

This agent lives in the [agents-lib](https://github.com/Waddah0-0/agents-lib) monorepo, in
[`agents/echo`](https://github.com/Waddah0-0/agents-lib/tree/main/agents/echo). It is not mirrored to a separate repository,
because it is a test fixture and template rather than a real agent.

Run its tests with `uv run pytest agents/echo`.
