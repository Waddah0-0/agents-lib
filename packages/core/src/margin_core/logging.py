"""Logging helpers. All library loggers live under the ``margin`` namespace."""

import logging

LOGGER_NAME = "margin"


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger under the ``margin`` namespace."""
    return logging.getLogger(f"{LOGGER_NAME}.{name}" if name else LOGGER_NAME)


def configure_logging(level: str | int = "INFO") -> None:
    """Configure a simple stderr handler for the library namespace (idempotent)."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
