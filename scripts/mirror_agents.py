"""Mirror each agent folder, with its own history, to its own GitHub repository.

For every agent whose ``[tool.margin]`` table has a ``mirror`` key, the folder's history
is extracted with ``git subtree split`` (deterministic, so repeated runs produce the same
commits) and pushed to the mirror's ``main`` branch. It never force-pushes: if the mirror
has commits that are not in the split, the run fails and asks for a manual look.

Usage::

    python scripts/mirror_agents.py            # dry run: only computes the splits
    MIRROR_TOKEN=... python scripts/mirror_agents.py --push

The token is a fine-grained personal access token with Contents read/write on the mirror
repositories only. It is passed to git through an HTTP header, never in a URL or log.
"""

from __future__ import annotations

import argparse
import base64
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_agents import ROOT, agent_dirs, load_meta


class MirrorError(Exception):
    """A mirror could not be updated safely."""


@dataclass(frozen=True)
class MirrorTarget:
    agent_id: str
    prefix: str  # e.g. agents/ai_code_detector
    repo: str  # e.g. Waddah0-0/margin-ai-code-detector


def mirror_targets(root: Path = ROOT) -> list[MirrorTarget]:
    targets = []
    for agent_dir in agent_dirs(root):
        meta = load_meta(agent_dir)
        if meta.mirror and meta.stage != "planned":
            prefix = agent_dir.relative_to(root).as_posix()
            targets.append(MirrorTarget(meta.id, prefix, meta.mirror))
    return targets


def _git(root: Path, *args: str, extra_config: list[str] | None = None) -> str:
    config: list[str] = []
    for item in extra_config or []:
        config += ["-c", item]
    proc = subprocess.run(
        ["git", *config, *args],
        cwd=root,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        check=False,
    )
    if proc.returncode != 0:
        raise MirrorError(f"git {args[0]} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def split(root: Path, prefix: str, ref: str = "HEAD") -> str:
    """Return the SHA of the subtree split of ``prefix`` at ``ref``."""
    sha = _git(root, "subtree", "split", f"--prefix={prefix}", ref)
    return sha.splitlines()[-1].strip()


def push(root: Path, target: MirrorTarget, sha: str, token: str, *, url: str | None = None) -> str:
    """Fast-forward the mirror's main branch to ``sha``. Returns what happened.

    ``url`` overrides the GitHub URL (tests push to a local bare repository).
    """
    url = url or f"https://github.com/{target.repo}.git"
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    auth = [f"http.https://github.com/.extraheader=AUTHORIZATION: basic {basic}"]
    remote_ref = f"refs/mirror-check/{target.agent_id}"
    try:
        _git(root, "fetch", "--quiet", url, f"+refs/heads/main:{remote_ref}", extra_config=auth)
        remote = _git(root, "rev-parse", remote_ref)
    except MirrorError:
        remote = ""  # empty repository: no main branch yet
    if remote:
        if remote == sha or _is_ancestor(root, sha, remote):
            return "up to date"
        if not _is_ancestor(root, remote, sha):
            raise MirrorError(
                f"{target.repo} has commits that are not in the monorepo; it was edited directly. "
                "Inspect it by hand; this script never force-pushes."
            )
    _git(root, "push", "--quiet", url, f"{sha}:refs/heads/main", extra_config=auth)
    return "pushed"


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant], cwd=root, check=False
    )
    return proc.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mirror agent folders to their own repos.")
    parser.add_argument("--push", action="store_true", help="push (default: dry run)")
    args = parser.parse_args(argv)
    token = os.environ.get("MIRROR_TOKEN", "")
    if args.push and not token:
        print("MIRROR_TOKEN is not set; running as a dry run.")
    targets = mirror_targets()
    if not targets:
        print("No agents are configured for mirroring.")
        return 0
    failed = False
    for target in targets:
        try:
            sha = split(ROOT, target.prefix)
            if args.push and token:
                outcome = push(ROOT, target, sha, token)
            else:
                outcome = "dry run"
            print(f"{target.agent_id}: {target.prefix} -> {target.repo} @ {sha[:12]} ({outcome})")
        except MirrorError as exc:
            failed = True
            print(f"{target.agent_id}: FAILED: {exc}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
