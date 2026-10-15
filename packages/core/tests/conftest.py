"""Shared fixtures for core tests. Git fixtures build real repos locally (no network)."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

GitRunner = Callable[..., str]

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def _git(repo: Path, *args: str, date: str = "2024-01-01T12:00:00+00:00") -> str:
    env = {
        "GIT_AUTHOR_DATE": date,
        "GIT_COMMITTER_DATE": date,
        "GIT_TERMINAL_PROMPT": "0",
    }
    import os

    proc = subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test User",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.autocrlf=false",
            *args,
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        env={**os.environ, **env},
        check=True,
    )
    return proc.stdout


@pytest.fixture
def git() -> GitRunner:
    """Run git in a given repo with deterministic identity and no signing."""
    return _git


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A git repo with two commits, one carrying an AI co-author trailer."""
    if shutil.which("git") is None:
        pytest.skip("git not installed")
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "app.py").write_text("print('hello')\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "Initial commit", date="2024-01-01T10:00:00+00:00")
    (repo / "util.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        "Add util\n\nCo-authored-by: Claude <noreply@anthropic.com>",
        date="2024-01-02T10:00:00+00:00",
    )
    return repo
