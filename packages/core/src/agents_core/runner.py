"""One-call convenience API for running an agent from Python."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from agents_core.agent import RunContext
from agents_core.llm.base import LLMClient
from agents_core.models import AgentResult
from agents_core.registry import AgentRegistry, default_registry


async def run_agent(
    agent_id: str,
    input: BaseModel | Mapping[str, Any],
    *,
    llm: LLMClient | None = None,
    config: Mapping[str, Any] | None = None,
    ctx: RunContext | None = None,
    registry: AgentRegistry | None = None,
) -> AgentResult:
    """Look up ``agent_id`` in the registry and execute it with ``input``."""
    agent = (registry or default_registry()).create(agent_id, llm=llm, config=config)
    return await agent.execute(input, ctx)
