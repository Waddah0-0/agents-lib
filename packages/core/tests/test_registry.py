"""Registry tests using a fake agent package written to a temp dir."""

from __future__ import annotations

import textwrap
from importlib.metadata import EntryPoint
from pathlib import Path

import pytest
from margin_core import AgentLoadError, AgentNotFoundError, AgentRegistry, BaseAgent
from margin_core.registry import ENTRY_POINT_GROUP

FAKE_PACKAGE = textwrap.dedent(
    """
    from pydantic import BaseModel
    from margin_core import AgentInput, BaseAgent

    class In(AgentInput):
        x: int = 0

    class Out(BaseModel):
        y: int = 0

    class Alpha(BaseAgent):
        id = "alpha"
        name = "Alpha"
        description = "first"
        version = "0.0.1"
        InputModel = In
        OutputModel = Out

        async def run(self, input, ctx):
            return self.make_result(summary="alpha", output=Out(y=input.x))

    class AlphaClone(Alpha):
        pass

    class NotAnAgent:
        pass
    """
)


def _ep(name: str, value: str) -> EntryPoint:
    return EntryPoint(name=name, value=value, group=ENTRY_POINT_GROUP)


@pytest.fixture
def fake_pkg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    pkg = tmp_path / "fake_agents_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(FAKE_PACKAGE, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    return "fake_agents_pkg"


def test_discovers_valid_agents(fake_pkg: str) -> None:
    registry = AgentRegistry([_ep("alpha", f"{fake_pkg}:Alpha")])
    assert registry.ids() == ["alpha"]
    cls = registry.get_agent_class("alpha")
    assert issubclass(cls, BaseAgent)
    assert registry.list_agents()[0].name == "Alpha"


def test_broken_entry_points_are_reported_not_raised(fake_pkg: str) -> None:
    registry = AgentRegistry(
        [
            _ep("alpha", f"{fake_pkg}:Alpha"),
            _ep("missing", "does_not_exist_pkg:Agent"),
            _ep("wrong", f"{fake_pkg}:NotAnAgent"),
            _ep("dupe", f"{fake_pkg}:AlphaClone"),
        ]
    )
    assert registry.ids() == ["alpha"]
    errors = registry.load_errors
    assert set(errors) == {"missing", "wrong", "dupe"}
    assert "not a BaseAgent" in errors["wrong"]
    assert "Duplicate" in errors["dupe"]
    with pytest.raises(AgentLoadError):
        registry.get_agent_class("missing")


def test_unknown_agent_lists_available(fake_pkg: str) -> None:
    registry = AgentRegistry([_ep("alpha", f"{fake_pkg}:Alpha")])
    with pytest.raises(AgentNotFoundError, match="alpha"):
        registry.get_agent_class("nope")


async def test_create_and_execute(fake_pkg: str) -> None:
    registry = AgentRegistry([_ep("alpha", f"{fake_pkg}:Alpha")])
    result = await registry.create("alpha").execute({"x": 7})
    assert result.data == {"y": 7}


def test_manual_registration(fake_pkg: str) -> None:
    registry = AgentRegistry([])
    module = __import__(fake_pkg)
    registry.register(module.Alpha)
    assert registry.ids() == ["alpha"]
