"""Discover installed agents through the ``margin.agents`` entry-point group."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from importlib.metadata import EntryPoint, entry_points
from typing import Any

from margin_core.agent import BaseAgent
from margin_core.errors import AgentLoadError, AgentNotFoundError
from margin_core.llm.base import LLMClient
from margin_core.logging import get_logger
from margin_core.models import AgentInfo

ENTRY_POINT_GROUP = "margin.agents"

logger = get_logger("registry")


class AgentRegistry:
    """Lazily discovers agents from entry points (or an explicit list, for tests).

    Broken entry points never break discovery: they are recorded in :attr:`load_errors`.
    """

    def __init__(self, entry_points: Iterable[EntryPoint] | None = None) -> None:
        self._entry_points = list(entry_points) if entry_points is not None else None
        self._agents: dict[str, type[BaseAgent]] | None = None
        self._manual: dict[str, type[BaseAgent]] = {}
        self._errors: dict[str, str] = {}

    def register(self, agent_cls: type[BaseAgent]) -> None:
        """Register an agent class manually (takes precedence over entry points)."""
        self._manual[agent_cls.id] = agent_cls

    def refresh(self) -> None:
        """Forget cached discovery results."""
        self._agents = None
        self._errors = {}

    @property
    def load_errors(self) -> dict[str, str]:
        self._discover()
        return dict(self._errors)

    def _discover(self) -> dict[str, type[BaseAgent]]:
        if self._agents is None:
            eps = (
                self._entry_points
                if self._entry_points is not None
                else list(entry_points(group=ENTRY_POINT_GROUP))
            )
            found: dict[str, type[BaseAgent]] = {}
            for ep in eps:
                try:
                    obj = ep.load()
                except Exception as exc:
                    self._errors[ep.name] = f"Failed to import {ep.value}: {exc}"
                    logger.warning("Could not load agent entry point %s: %s", ep.name, exc)
                    continue
                if not (isinstance(obj, type) and issubclass(obj, BaseAgent)):
                    self._errors[ep.name] = f"{ep.value} is not a BaseAgent subclass"
                    continue
                if obj.id in found and found[obj.id] is not obj:
                    self._errors[ep.name] = f"Duplicate agent id {obj.id!r}"
                    continue
                if obj.id != ep.name:
                    logger.warning("Entry point %r registers agent id %r", ep.name, obj.id)
                found[obj.id] = obj
            self._agents = found
        return {**self._agents, **self._manual}

    def get_agent_class(self, agent_id: str) -> type[BaseAgent]:
        agents = self._discover()
        if agent_id not in agents:
            if agent_id in self._errors:
                raise AgentLoadError(self._errors[agent_id])
            available = ", ".join(sorted(agents)) or "none"
            raise AgentNotFoundError(f"No agent {agent_id!r}. Available agents: {available}")
        return agents[agent_id]

    def create(
        self,
        agent_id: str,
        *,
        llm: LLMClient | None = None,
        config: Mapping[str, Any] | None = None,
    ) -> BaseAgent:
        return self.get_agent_class(agent_id)(llm=llm, config=config)

    def list_agents(self) -> list[AgentInfo]:
        return [cls.info() for _, cls in sorted(self._discover().items())]

    def ids(self) -> list[str]:
        return sorted(self._discover())


_default_registry = AgentRegistry()


def default_registry() -> AgentRegistry:
    """The process-wide registry backed by installed entry points."""
    return _default_registry


def list_agents() -> list[AgentInfo]:
    return _default_registry.list_agents()


def get_agent(agent_id: str) -> type[BaseAgent]:
    return _default_registry.get_agent_class(agent_id)
