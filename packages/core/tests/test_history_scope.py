"""Git history scoped to the workspace, blobless-safe history helpers, Workspace.exists."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from agents_core.loaders import LocalLoader
from agents_core.loaders.git import read_changed_files_sync

GitRunner = Callable[..., str]


@pytest.fixture
def mono(tmp_path: Path, git: GitRunner) -> Path:
    """A repo with two sub-projects and commits touching each, plus one touching both."""
    repo = tmp_path / "mono"
    (repo / "app").mkdir(parents=True)
    (repo / "lib").mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "app" / "main.py").write_text("print(1)\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "app: start", date="2024-01-01T10:00:00+00:00")
    (repo / "lib" / "util.py").write_text("X = 1\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "lib: start", date="2024-01-02T10:00:00+00:00")
    (repo / "app" / "main.py").write_text("print(2)\n", encoding="utf-8")
    (repo / "lib" / "util.py").write_text("X = 2\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "both: bump", date="2024-01-03T10:00:00+00:00")
    return repo


async def test_whole_repo_history(mono: Path) -> None:
    ws = await LocalLoader().load(str(mono))
    assert ws.git is not None and ws.git.prefix == "" and ws.git.pathspecs == []
    assert [c.subject for c in await ws.git.commits()] == ["both: bump", "lib: start", "app: start"]


async def test_subfolder_history_is_scoped(mono: Path) -> None:
    ws = await LocalLoader().load(str(mono / "app"))
    assert ws.git is not None and ws.git.prefix == "app"
    assert [c.subject for c in await ws.git.commits()] == ["both: bump", "app: start"]
    history = await ws.git.file_history()
    assert set(history) == {"main.py"}  # workspace-relative, lib/ excluded
    assert len(history["main.py"]) == 2


async def test_paths_restriction_scopes_history(mono: Path) -> None:
    ws = await LocalLoader().load(str(mono), paths=["lib"])
    assert ws.git is not None and ws.git.pathspecs == ["lib"]
    assert [c.subject for c in await ws.git.commits()] == ["both: bump", "lib: start"]


async def test_single_file_target_scopes_history(mono: Path) -> None:
    ws = await LocalLoader().load(str(mono / "lib" / "util.py"))
    assert ws.git is not None and ws.git.pathspecs == ["lib/util.py"]
    changed = await ws.git.changed_files()
    assert all(paths == ["util.py"] for paths in changed.values())
    assert len(changed) == 2


def _missing_blobs(repo: Path) -> int:
    out = subprocess.run(
        ["git", "rev-list", "--objects", "--all", "--missing=print"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sum(1 for line in out.splitlines() if line.startswith("?"))


def test_name_only_history_fetches_no_blobs(mono: Path, tmp_path: Path, git: GitRunner) -> None:
    git(mono, "config", "uploadpack.allowFilter", "true")
    clone = tmp_path / "blobless"
    git(tmp_path, "clone", "-q", "--filter=blob:none", "--no-checkout", mono.as_uri(), str(clone))
    before = _missing_blobs(clone)
    if before == 0:
        pytest.skip("this git build ignored --filter for file:// clones")

    changes = read_changed_files_sync(clone)
    assert [len(paths) for _, paths in changes] == [2, 1, 1]
    assert _missing_blobs(clone) == before  # nothing was downloaded

    git(clone, "log", "--numstat")  # control: proves the counter detects blob fetches
    assert _missing_blobs(clone) < before


async def test_workspace_exists_sees_ignored_dirs(tmp_path: Path) -> None:
    (tmp_path / ".cursor" / "rules").mkdir(parents=True)
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    ws = await LocalLoader().load(str(tmp_path))
    assert ws.exists(".cursor/rules")
    assert ws.exists("node_modules")
    assert not ws.exists("CLAUDE.md")
    assert not ws.exists("../outside")
    assert not ws.exists("/etc/passwd")
