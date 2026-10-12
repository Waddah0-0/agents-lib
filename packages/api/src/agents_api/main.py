"""FastAPI application entrypoint."""

from fastapi import FastAPI

app = FastAPI(
    title="agents-lib API",
    version="0.1.0",
    description="HTTP API for agents-lib",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Healthcheck endpoint."""
    return {"status": "ok"}
