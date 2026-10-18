"""Thin wrappers around the ``git`` CLI. Repository code is never executed."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from agents_core.loaders.base import GitCommit, GitInfo
from agents_core.logging import get_logger

logger = get_logger("git")

RECORD_SEP = "\x1e"
FIELD_SEP = "\x1f"
_LOG_FORMAT = RECORD_SEP + FIELD_SEP.join(
    ["%H", "%an", "%ae", "%aI", "%cn", "%ce", "%cI", "%P", "%B"]
)


class GitCommandError(RuntimeError):
    """A git command exited with a non-zero status."""


def git_available() -> bool:
    return shutil.which("git") is not None


def safe_git_env() -> dict[str, str]:
    """Environment that prevents git from ever prompting (terminal, GUI, credential manager)."""
    env = dict(os.environ)
    env.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "",
            "SSH_ASKPASS": "",
            "GCM_INTERACTIVE": "never",
        }
    )
    return env


def run_git(args: list[str], cwd: Path | None = None, timeout_s: float = 60.0) -> str:
    """Run ``git <args>`` and return stdout (UTF-8). Raises :class:`GitCommandError`."""
    cmd = ["git", "-c", "i18n.logOutputEncoding=UTF-8", *args]
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        timeout=timeout_s,
        env=safe_git_env(),
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise GitCommandError(f"git {' '.join(args)} failed: {stderr}")
    return proc.stdout.decode("utf-8", errors="replace")


def detect_git(path: Path, scopes: list[str] | None = None) -> GitInfo | None:
    """Return :class:`GitInfo` if ``path`` is inside a git work tree, else ``None``.

    History is limited to ``path`` (when it is a sub-folder of the repository) and, within
    it, to ``scopes`` (workspace-relative paths), so commit signals only describe the code
    being analysed.
    """
    if not git_available():
        return None
    try:
        top = run_git(["rev-parse", "--show-toplevel"], cwd=path).strip()
    except (GitCommandError, OSError, subprocess.TimeoutExpired):
        return None
    root = Path(top)
    try:
        prefix = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        logger.warning("Could not place %s inside repository %s; using full history", path, root)
        prefix = "."
    prefix = "" if prefix == "." else prefix
    pathspecs = [f"{prefix}/{s}" if prefix else s for s in scopes or [] if s]
    if not pathspecs and prefix:
        pathspecs = [prefix]
    head: str | None
    try:
        head = run_git(["rev-parse", "HEAD"], cwd=root).strip()
    except GitCommandError:
        head = None  # repository without commits
    try:
        branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=root).strip() or None
    except GitCommandError:
        branch = None
    return GitInfo(root=root, head=head, branch=branch, prefix=prefix, pathspecs=pathspecs)


def parse_log(output: str) -> list[GitCommit]:
    """Parse output produced with :data:`_LOG_FORMAT`."""
    commits: list[GitCommit] = []
    for record in output.split(RECORD_SEP):
        if not record.strip():
            continue
        fields = record.split(FIELD_SEP, 8)
        if len(fields) != 9:
            logger.warning("Skipping malformed git log record")
            continue
        sha, an, ae, ad, cn, ce, cd, parents, message = fields
        commits.append(
            GitCommit(
                sha=sha.strip(),
                author_name=an,
                author_email=ae,
                authored_at=datetime.fromisoformat(ad),
                committer_name=cn,
                committer_email=ce,
                committed_at=datetime.fromisoformat(cd),
                parents=parents.split(),
                message=message.strip("\n"),
            )
        )
    return commits


def _pathspec_args(pathspecs: list[str] | None) -> list[str]:
    return ["--", *pathspecs] if pathspecs else []


def read_commits_sync(
    root: Path, max_count: int | None = None, pathspecs: list[str] | None = None
) -> list[GitCommit]:
    args = ["log", f"--format={_LOG_FORMAT}"]
    if max_count is not None:
        args.append(f"--max-count={max_count}")
    return parse_log(run_git(args + _pathspec_args(pathspecs), cwd=root, timeout_s=120.0))


async def read_commits(
    root: Path, max_count: int | None = None, pathspecs: list[str] | None = None
) -> list[GitCommit]:
    return await asyncio.to_thread(read_commits_sync, root, max_count, pathspecs)


def read_changed_files_sync(
    root: Path, pathspecs: list[str] | None = None
) -> list[tuple[str, list[str]]]:
    """``(sha, repo-relative paths)`` per commit, newest first, without reading any blob.

    Only ``--name-only --no-renames`` is safe on blobless clones: ``--numstat``, ``--stat``,
    ``-p`` and rename detection need file contents and would download every historical blob
    (verified 2026-10-18: ``--numstat`` fetched all 97 missing blobs of a test clone).
    """
    args = [
        "-c",
        "core.quotepath=off",
        "log",
        "--name-only",
        "--no-renames",
        f"--format={RECORD_SEP}%H",
    ]
    output = run_git(args + _pathspec_args(pathspecs), cwd=root, timeout_s=120.0)
    changes: list[tuple[str, list[str]]] = []
    for record in output.split(RECORD_SEP):
        lines = [line for line in record.splitlines() if line.strip()]
        if lines:
            changes.append((lines[0].strip(), lines[1:]))
    return changes


async def read_changed_files(
    root: Path, pathspecs: list[str] | None = None
) -> list[tuple[str, list[str]]]:
    return await asyncio.to_thread(read_changed_files_sync, root, pathspecs)
