# margin-api

An HTTP server that runs any installed margin agent in the background, so a web UI or
any other program can start runs, follow their progress live and fetch their results.

## Starting it

```bash
uv run margin-api            # http://127.0.0.1:8000, interactive docs at /docs
```

It listens on `127.0.0.1` only, so nothing on your network can reach it. Settings come from
environment variables (or `.env`) prefixed with `MARGIN_API_`:

| Setting | Default | Meaning |
|---|---|---|
| `MARGIN_API_HOST` / `MARGIN_API_PORT` | `127.0.0.1` / `8000` | Where to listen. Change the host only if you mean to expose it. |
| `MARGIN_API_CORS_ORIGINS` | `["http://localhost:3000", "http://127.0.0.1:3000"]` | Web pages allowed to call it (JSON list). |
| `MARGIN_API_LLM_CONCURRENCY` | `1` | Runs of agents that use a model, at once (one local GPU). |
| `MARGIN_API_OTHER_CONCURRENCY` | `4` | Runs of other agents, at once. |
| `MARGIN_API_RESULT_TTL_S` | `3600` | Seconds a finished run is kept. |
| `MARGIN_API_MAX_BODY_BYTES` | `1000000` | Largest accepted request body. |
| `MARGIN_API_CANCEL_GRACE_S` | `30` | Time a cancelled run gets to stop on its own before it is stopped. |

Model settings (`DEFAULT_LLM_PROVIDER`, `LOCAL_LLM_BASE_URL`, ...) are the same as for the CLI.

## Endpoints

| Method and path | What it does |
|---|---|
| `GET /health` | Liveness check. |
| `GET /agents` | Installed agents with their input and output JSON schemas, plus any that failed to load. |
| `GET /agents/{id}` | One agent. |
| `POST /agents/{id}/runs` | Start a run. The body is the agent's input as JSON. Answers `202` with the `run_id`. |
| `GET /runs/{run_id}` | Status (`queued`, `running`, `done`, `cancelled`), queue position, latest progress and, when done, the result. |
| `GET /runs/{run_id}/events` | Server-sent events: `status`, `progress`, then one final `result`. |
| `DELETE /runs/{run_id}` | Cancel a run. |
| `GET /runs` | Recent runs. |

## Example with curl

```bash
# start a run
curl -s -X POST http://127.0.0.1:8000/agents/echo/runs \
     -H 'content-type: application/json' -d '{"message": "hello", "repeat": 2}'
# -> {"run_id": "342e1c...", "status": "queued", "queue_position": 1, "links": {...}}

# follow it live (the stream ends with a "result" event)
curl -N http://127.0.0.1:8000/runs/342e1c.../events

# or poll it, or cancel it
curl -s http://127.0.0.1:8000/runs/342e1c...
curl -s -X DELETE http://127.0.0.1:8000/runs/342e1c...
```

## How runs behave

- **Asynchronous.** Starting a run returns at once; the work happens in the background.
- **Queues.** Agents that use a model (such as the AI Code Detector) share one queue, one run
  at a time by default, because a local model has one GPU. Other margin run up to four at a
  time. A queued run reports its position.
- **Late subscribers miss nothing.** Each run keeps its last 200 events, and the event stream
  starts with that history. Reconnecting with the standard `Last-Event-ID` header resumes
  after the last event received.
- **Failures are results.** If an agent fails, the run still ends as `done`, and its result
  has `status: "error"` with the reason. HTTP errors mean the request itself was wrong:
  `404` unknown agent or run, `422` input that does not match the agent's schema, `413` body
  too large, `500` an agent that failed to load.
- **Cancelling** asks the agent to stop at its next checkpoint (a model call in progress is
  allowed to finish). An agent that has not stopped after the grace period is stopped.
- **Memory only.** Runs are kept in memory and forgotten after an hour, or when the server
  restarts.

## For UI developers

The OpenAPI schema is exported to `ui/openapi.json` by `scripts/export_openapi.py`, and CI
fails if it falls out of date, so a typed client can be generated from it safely.
