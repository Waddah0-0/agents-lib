"""Shared HTTP helper for REST-based LLM providers."""

from __future__ import annotations

from typing import Any

import httpx

from margin_core.errors import LLMError, TransientLLMError


async def post_json(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_s: float,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """POST JSON and return the decoded object, mapping failures onto LLM errors."""
    try:
        if client is not None:
            response = await client.post(url, headers=headers, json=payload, timeout=timeout_s)
        else:
            async with httpx.AsyncClient(timeout=timeout_s) as owned:
                response = await owned.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise TransientLLMError(f"Request timed out: {exc}") from exc
    except httpx.TransportError as exc:
        raise TransientLLMError(f"Network error: {exc}") from exc

    if response.status_code == 429 or response.status_code >= 500:
        raise TransientLLMError(f"HTTP {response.status_code}: {response.text[:500]}")
    if response.status_code >= 400:
        raise LLMError(f"HTTP {response.status_code}: {response.text[:500]}")
    try:
        data = response.json()
    except ValueError as exc:
        raise LLMError(f"Invalid JSON from provider: {response.text[:200]}") from exc
    if not isinstance(data, dict):
        raise LLMError("Unexpected response shape from provider")
    return data
