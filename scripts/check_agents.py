"""Check every agent folder against the sub-repo standard (PLAN.md §5.11).

Each agent under ``agents/`` must be a self-contained sub-repo: standard files, a README
with the required sections, matching ids and versions, and nothing that points outside the
folder (so the mirror repository works on its own).

Usage: ``uv run python scripts/check_agents.py``  (exit code 1 when anything is wrong)
"""

from __future__ import annotations

import importlib
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ENTRY_POINT_GROUP = "agents_lib.agents"
STAGES = ("planned", "experimental", "stable")
README_SECTIONS = (
    "What it does",
    "How it works",
    "Input",
    "Output",
    "Limits",
    "Usage",
    "Development",
)
ID_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
MD_LINK_OUTSIDE_RE = re.compile(r"\]\(\s*\.\./")
VERSION_RE = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.MULTILINE)


@dataclass(frozen=True)
class WorkspaceConfig:
    """Repository-wide settings from the root ``pyproject.toml`` ``[tool.agents-lib]``."""

    repository: str
    mirror_owner: str


@dataclass(frozen=True)
class AgentMeta:
    """What an agent folder declares about itself."""

    dir: Path
    id: str
    stage: str
    mirror: str | None
    name: str
    version: str
    package: str | None
    entry_point: str | None
    pyproject: dict[str, Any]


def read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def workspace_config(root: Path = ROOT) -> WorkspaceConfig:
    table = read_toml(root / "pyproject.toml").get("tool", {}).get("agents-lib", {})
    return WorkspaceConfig(
        repository=str(table.get("repository", "")).rstrip("/"),
        mirror_owner=str(table.get("mirror-owner", "")),
    )


def agent_dirs(root: Path = ROOT) -> list[Path]:
    return sorted(p for p in (root / "agents").iterdir() if (p / "pyproject.toml").is_file())


def load_meta(agent_dir: Path) -> AgentMeta:
    data = read_toml(agent_dir / "pyproject.toml")
    project = data.get("project", {})
    tool = data.get("tool", {}).get("agents-lib", {})
    packages = data.get("tool", {}).get("hatch", {}).get("build", {}).get("targets", {})
    wheel_packages = packages.get("wheel", {}).get("packages", [])
    entry_points = project.get("entry-points", {}).get(ENTRY_POINT_GROUP, {})
    package = None
    if len(wheel_packages) == 1 and str(wheel_packages[0]).startswith("src/"):
        package = str(wheel_packages[0])[len("src/") :]
    agent_id = str(tool.get("id", ""))
    return AgentMeta(
        dir=agent_dir,
        id=agent_id,
        stage=str(tool.get("stage", "")),
        mirror=tool.get("mirror"),
        name=str(project.get("name", "")),
        version=str(project.get("version", "")),
        package=package,
        entry_point=entry_points.get(agent_id) if isinstance(entry_points, dict) else None,
        pyproject=data,
    )


def _readme_problems(readme: Path) -> list[str]:
    if not readme.is_file():
        return ["README.md is missing"]
    headings = [line[3:].strip() for line in readme.read_text(encoding="utf-8").splitlines()
                if line.startswith("## ")]  # fmt: skip
    missing = [s for s in README_SECTIONS if s not in headings]
    if missing:
        return [f"README.md is missing sections: {', '.join(missing)}"]
    order = [headings.index(s) for s in README_SECTIONS]
    if order != sorted(order):
        return [f"README.md sections must appear in this order: {', '.join(README_SECTIONS)}"]
    return []


def _class_problems(meta: AgentMeta) -> list[str]:
    from agents_core import BaseAgent

    assert meta.entry_point is not None
    module_name, _, attr = meta.entry_point.partition(":")
    src = str(meta.dir / "src")
    added = src not in sys.path
    if added:
        sys.path.insert(0, src)
    try:
        cls = getattr(importlib.import_module(module_name), attr)
    except Exception as exc:
        return [f"entry point {meta.entry_point!r} cannot be imported: {exc}"]
    finally:
        if added:
            sys.path.remove(src)
    if not (isinstance(cls, type) and issubclass(cls, BaseAgent)):
        return [f"entry point {meta.entry_point!r} is not a BaseAgent subclass"]
    problems = []
    if cls.id != meta.id:
        problems.append(f"class id {cls.id!r} differs from [tool.agents-lib] id {meta.id!r}")
    if cls.version != meta.version:
        problems.append(f"class version {cls.version!r} differs from pyproject {meta.version!r}")
    return problems


def check_agent(agent_dir: Path, root: Path = ROOT, *, import_classes: bool = True) -> list[str]:
    """Return a list of problems with one agent folder (empty when it follows the standard)."""
    problems: list[str] = []
    meta = load_meta(agent_dir)
    config = workspace_config(root)
    rel = agent_dir.relative_to(root).as_posix()
    pyproject_text = (agent_dir / "pyproject.toml").read_text(encoding="utf-8")

    # identity
    if not ID_RE.match(meta.id):
        return [f"[tool.agents-lib] id {meta.id!r} is missing or not kebab-case"]
    if agent_dir.name != meta.id.replace("-", "_"):
        problems.append(f"folder should be named {meta.id.replace('-', '_')!r}")
    if meta.name != f"agents-lib-{meta.id}":
        problems.append(f"project name should be 'agents-lib-{meta.id}', not {meta.name!r}")
    if meta.stage not in STAGES:
        problems.append(f"[tool.agents-lib] stage must be one of {', '.join(STAGES)}")
    if meta.mirror is not None:
        expected = f"{config.mirror_owner}/agents-lib-{meta.id}"
        if meta.mirror != expected:
            problems.append(f"mirror should be {expected!r}, not {meta.mirror!r}")
        if meta.stage == "planned":
            problems.append("planned agents are not mirrored; remove 'mirror' until it works")

    # self-containment
    if "[tool.uv.sources]" in pyproject_text:
        problems.append("pyproject.toml must not have [tool.uv.sources] (the root provides it)")
    if "../" in pyproject_text:
        problems.append("pyproject.toml refers to a path outside the folder ('../')")
    for md in sorted(agent_dir.rglob("*.md")):
        if MD_LINK_OUTSIDE_RE.search(md.read_text(encoding="utf-8")):
            problems.append(f"{md.relative_to(agent_dir).as_posix()} links outside the folder")
    deps = meta.pyproject.get("project", {}).get("dependencies", [])
    if not any(str(d).split()[0].startswith("agents-lib-core") for d in deps):
        problems.append("dependencies must include agents-lib-core")

    # standard files
    problems += _readme_problems(agent_dir / "README.md")
    changelog = agent_dir / "CHANGELOG.md"
    if not changelog.is_file():
        problems.append("CHANGELOG.md is missing")
    elif f"## [{meta.version}]" not in changelog.read_text(encoding="utf-8"):
        problems.append(f"CHANGELOG.md has no '## [{meta.version}]' entry for the current version")
    license_file = agent_dir / "LICENSE"
    root_license = (root / "LICENSE").read_text(encoding="utf-8").strip()
    if not license_file.is_file():
        problems.append("LICENSE is missing (copy the root LICENSE)")
    elif license_file.read_text(encoding="utf-8").strip() != root_license:
        problems.append("LICENSE differs from the root LICENSE")
    if not list((agent_dir / "tests").glob("test_*.py")):
        problems.append("tests/ has no test_*.py files")

    # package
    if meta.package is None:
        problems.append("[tool.hatch.build.targets.wheel] packages must be ['src/<package>']")
    else:
        pkg = agent_dir / "src" / meta.package
        for required in ("__init__.py", "py.typed"):
            if not (pkg / required).is_file():
                problems.append(f"src/{meta.package}/{required} is missing")
        init = pkg / "__init__.py"
        found = VERSION_RE.search(init.read_text(encoding="utf-8")) if init.is_file() else None
        if found is None or found.group(1) != meta.version:
            problems.append(f"src/{meta.package}/__init__.py __version__ must be {meta.version!r}")
        if meta.stage != "planned":
            for required in ("agent.py", "models.py"):
                if not (pkg / required).is_file():
                    problems.append(f"src/{meta.package}/{required} is missing")

    # registration
    if meta.entry_point is None:
        if meta.stage != "planned":
            problems.append(f"entry point '{meta.id}' in '{ENTRY_POINT_GROUP}' is missing")
    elif import_classes:
        problems += _class_problems(meta)

    # workspace wiring
    root_data = read_toml(root / "pyproject.toml")
    if f"agents-lib-{meta.id}" not in root_data.get("tool", {}).get("uv", {}).get("sources", {}):
        problems.append(f"root pyproject [tool.uv.sources] lacks agents-lib-{meta.id}")
    if f"{rel}/src" not in root_data.get("tool", {}).get("mypy", {}).get("mypy_path", []):
        problems.append(f"root pyproject [tool.mypy] mypy_path lacks {rel}/src")
    if f"({rel}/README.md)" not in (root / "README.md").read_text(encoding="utf-8"):
        problems.append(f"root README agents table has no link to {rel}/README.md")
    return problems


def check_all(root: Path = ROOT, *, import_classes: bool = True) -> dict[str, list[str]]:
    return {d.name: check_agent(d, root, import_classes=import_classes) for d in agent_dirs(root)}


def main() -> int:
    results = check_all()
    for name, problems in results.items():
        if problems:
            print(f"FAIL agents/{name}")
            for problem in problems:
                print(f"     - {problem}")
        else:
            print(f"ok   agents/{name}")
    return 1 if any(results.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
