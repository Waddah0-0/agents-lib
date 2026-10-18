# Echo

The smallest possible agent. It echoes its input back and can optionally ask the
configured model to reply.

It has two uses:

- smoke-testing the toolchain (registry, CLI, API, UI) without network access;
- serving as a reference to copy when you write a new agent. See
  [writing an agent](../../docs/writing-an-agent.md).

## Input

| Field | Type | Default | Meaning |
|---|---|---|---|
| `message` | text | required | The text to echo. |
| `repeat` | 1 to 10 | 1 | How many times to repeat it. |
| `use_llm` | true/false | false | Also send the message to the model and include its reply. |

## Usage

```python
import asyncio
from agents_core import run_agent


async def main() -> None:
    result = await run_agent("echo", {"message": "hello", "repeat": 2})
    print(result.data["echoed"])  # hello hello


asyncio.run(main())
```
