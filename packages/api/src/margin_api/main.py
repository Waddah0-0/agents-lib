"""Entry point: ``margin-api`` starts the server (``MARGIN_API_HOST``/``MARGIN_API_PORT``)."""

from __future__ import annotations

from margin_api.app import create_app
from margin_api.settings import load_settings


def run() -> None:
    import uvicorn

    settings = load_settings()
    uvicorn.run(create_app(settings=settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    run()
