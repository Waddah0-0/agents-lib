"""Entry point: ``agents-api`` starts the server (``AGENTS_API_HOST``/``AGENTS_API_PORT``)."""

from __future__ import annotations

from agents_api.app import create_app
from agents_api.settings import load_settings


def run() -> None:
    import uvicorn

    settings = load_settings()
    uvicorn.run(create_app(settings=settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    run()
