# agents-lib-cli

The `agents` command lists, describes and runs every agent installed with agents-lib.
Installing an agent package is enough for it to appear here.

## Commands

```bash
agents list [--json]                 # installed agents (and any that failed to load)
agents info <agent> [--json]         # description and input fields
agents run <agent> [INPUT] [options] # run it and print the report
agents version
```

`agents --verbose ...` (or `-v`) prints debug logs on stderr.

## Giving an agent its input

- **The positional value** fills the agent's main input field (shown as "positional" by
  `agents info`). For the detector that is the repository URL or path; for echo, the
  message.
- **`--set field=value`** (repeatable, short `-s`) sets any field. Values are read as JSON
  when they are valid JSON (`3`, `true`, `["a","b"]`), except for text fields, which always
  take the value as written.
- **`--input file.json`** (`-i`) reads fields from a JSON object. `--set` overrides it.

```bash
agents run echo hello --set repeat=3
agents run echo --set message=hello --set use_llm=true
agents run echo -i input.json -s repeat=1
```

Giving the main field both positionally and with `--set` is an error.

## Options of `agents run`

| Option | Meaning |
|---|---|
| `--format markdown\|json`, `-f` | Report format. Default: JSON when `--out` ends in `.json`, otherwise Markdown. |
| `--out PATH`, `-o` | Write the report to a file instead of stdout. |
| `--provider NAME` | LLM provider: `local` (default), `anthropic`, `openai` or `mock`. |
| `--model NAME` | Model name, e.g. `qwen3.5:9b`. |
| `--max-cost USD` | Spending limit for this run (only matters for hosted providers). |
| `--quiet`, `-q` | No progress display. |
| `--strict` | Treat a partial result as a failure (exit code 4). |

The LLM client is set up from your settings (`.env` or environment variables), but nothing
contacts a model unless the agent actually uses one. So agents that need no model run even
when no model server is running, and when the default provider cannot be set up at all.
A provider or model you choose with `--provider` or `--model` is checked straight away.

## Output streams

Only the report goes to stdout. Progress, warnings and errors go to stderr. This keeps
`agents run ... --format json > report.json` valid JSON.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | The run finished with status `ok`, or `partial` without `--strict`. |
| 1 | The run finished with status `error` (the report still explains why). |
| 2 | Bad usage or invalid input. |
| 3 | The agent is not installed, or failed to load. |
| 4 | The run finished with status `partial` and `--strict` was given. |
| 130 | Cancelled with Ctrl+C. |

## Cancelling

Press Ctrl+C once to ask the agent to stop. It gets 5 seconds to finish cleanly, after which
it is stopped. Press Ctrl+C again to stop at once.
