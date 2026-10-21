"""The security guarantees, each shown by an attempt to break it.

- a folder we are pointed at cannot make git run its programs (config, hooks, LFS);
- files outside the workspace cannot be read, by path or through a symlink;
- cancelling a run during a clone stops git and leaves nothing behind;
- secrets (API keys, the GitHub token) never appear in logs or error messages.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from margin_core.errors import InvalidTargetError
from margin_core.loaders import load_workspace
from margin_core.loaders.base import Workspace
from margin_core.loaders.git import SAFE_GIT_CONFIG, git_command, run_git
from margin_core.loaders.github import GitHubLoader

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo, check=True, capture_output=True,
    )  # fmt: skip


def _trap(marker: Path) -> str:
    """A command that, if git ever runs it, leaves ``marker`` behind."""
    script = f"open({str(marker)!r}, 'w').write('ran')"
    return f'"{sys.executable}" -c "{script}"'.replace("\\", "/")


# ---- 1. untrusted repository config -------------------------------------------------------


@needs_git
async def test_a_repository_cannot_make_git_run_its_programs(tmp_path: Path) -> None:
    repo, marker = tmp_path / "hostile", tmp_path / "fsmonitor-ran"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    # the repository's own config names a program for git to run on index reads
    _git(repo, "config", "core.fsmonitor", _trap(marker))

    # sanity: the trap is armed. Plain git, as a careless tool would call it, runs it.
    subprocess.run(["git", "status"], cwd=repo, capture_output=True, check=False)  # noqa: ASYNC221
    if not marker.exists():
        pytest.skip("this git does not run core.fsmonitor here; nothing to prove")
    marker.unlink()

    async with await load_workspace(str(repo)) as ws:
        assert ws.git is not None
        await ws.git.commits(max_count=10)
        await ws.git.changed_files(max_count=10)
    run_git(["status"], cwd=repo)  # even an index-reading command, through margin's wrapper
    assert not marker.exists(), "margin let the repository run a program"


def test_every_git_command_carries_the_safety_settings() -> None:
    cmd = git_command(["log"])
    for setting in SAFE_GIT_CONFIG:
        assert cmd[cmd.index(setting) - 1] == "-c"
    assert "core.fsmonitor=false" in cmd and "filter.lfs.smudge=" in cmd
    assert cmd[-1] == "log"


# ---- 2. reading outside the workspace ------------------------------------------------------


def test_paths_cannot_leave_the_workspace(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    (root / "ok.py").write_text("fine", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    ws = Workspace(root=root, source=str(root))
    assert ws.read_text("ok.py") == "fine"
    for escape in ["../secret.txt", "sub/../../secret.txt", str(tmp_path / "secret.txt")]:
        with pytest.raises(InvalidTargetError, match="escapes"):
            ws.read_text(escape)
    assert not ws.exists("../secret.txt")


def test_symlinks_cannot_lead_out_of_the_workspace(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    try:
        (root / "link.py").symlink_to(tmp_path / "secret.txt")
    except OSError:
        pytest.skip("symlinks not permitted on this system (covered on Linux CI)")
    with pytest.raises(InvalidTargetError, match="escapes"):
        Workspace(root=root, source=str(root)).read_text("link.py")


# ---- 3. cancelling during a clone ------------------------------------------------------------


@needs_git
async def test_cancelling_during_a_clone_stops_git_and_leaves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))  # where the clone folder goes
    started = tmp_path / "clone-started"
    # stands in for a long clone: keeps writing into the destination until killed
    slow_clone = (
        "import pathlib, sys, time\n"
        "dest = pathlib.Path(sys.argv[1]); dest.mkdir(parents=True)\n"
        f"pathlib.Path({str(started)!r}).write_text('1')\n"
        "for i in range(600):\n"
        "    (dest / f'f{i}').write_text('x'); time.sleep(0.05)\n"
    )
    loader = GitHubLoader(allow_non_github_urls=True)
    monkeypatch.setattr(
        loader, "_clone_command",
        lambda url, dest, branch: [sys.executable, "-c", slow_clone, str(dest)],
    )  # fmt: skip
    task = asyncio.create_task(loader.load("file:///anything"))
    for _ in range(100):
        if started.exists():
            break
        await asyncio.sleep(0.05)
    assert started.exists(), "the fake clone never started"
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0.3)  # a process that was not stopped would keep writing
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.startswith("margin-")]  # noqa: ASYNC240
    assert leftovers == [], f"cancelled clone left {leftovers}"


# ---- 4. secrets ------------------------------------------------------------------------------

SENTINEL = "sk-SENTINEL-0123456789abcdef"


async def test_secrets_never_reach_logs_or_errors(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import httpx
    from margin_core.config import get_settings
    from margin_core.llm import create_llm
    from margin_core.llm.catalog import check_connection, list_models

    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LOCAL_LLM_API_KEY", "GITHUB_TOKEN"):
        monkeypatch.setenv(name, SENTINEL)
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:9")  # nothing listens there
    caplog.set_level(logging.DEBUG)

    texts = [repr(get_settings()), str(get_settings().model_dump())]
    for provider in ("anthropic", "openai", "local"):
        texts.append(repr(create_llm(provider, "m")))
        texts.append((await check_connection(provider, "m")).message)
        try:
            await list_models(provider, timeout_s=2)
        except Exception as exc:  # noqa: BLE001 - we only care what the error says
            texts.append(str(exc))

    def refuse(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    loader = GitHubLoader(http_client=httpx.AsyncClient(transport=httpx.MockTransport(refuse)))
    texts.append(str(await loader.check_remote_size("owner", "repo")))

    everything = "\n".join(texts + [r.getMessage() for r in caplog.records])
    assert SENTINEL not in everything
    assert os.environ["GITHUB_TOKEN"] == SENTINEL  # it was set; it just never leaked
