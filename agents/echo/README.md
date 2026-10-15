# agents-lib-echo

The smallest possible agent. It echoes its input, and optionally asks the configured LLM to reply.

Use it to smoke-test the toolchain (registry, CLI, API, UI) without network access, and as a
reference when writing a new agent (see `docs/writing-an-agent.md`).

```python
from agents_core import run_agent

result = await run_agent("echo", {"message": "hello", "repeat": 2})
print(result.data["echoed"])  # "hello hello"
```
