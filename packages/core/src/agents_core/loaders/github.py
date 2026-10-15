"""Clone a public GitHub repository into a temporary workspace.

Security posture: only ``https://github.com/<owner>/<repo>`` URLs are accepted by default,
submodules are not fetched, symlinks are checked out as plain files, all credential prompts
are disabled, and the clone is size- and time-limited. Repository code is never executed.
"""

from __future__ import annotations

import asyncio
import re
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

from agents_core._fs import directory_size, force_rmtree
from agents_core.errors import InvalidTargetError, LimitExceededError, LoaderError
from agents_core.loaders.base import Loader, LoaderLimits, Workspace
from agents_core.loaders.filters import FilterConfig
from agents_core.loaders.git import GitCommandError, git_available, run_git
from agents_core.loaders.local import LocalLoader

GITHUB_URL_RE = re.compile(
    r"^https://github\.com/"
    r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/"
    r"(?P<repo>[A-Za-z0-9._-]{1,100}?)"
    r"(?:\.git)?/?$"
)
BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")


def parse_github_url(url: str) -> tuple[str, str]:
    """Return ``(owner, repo)`` for a valid GitHub repository URL."""
    match = GITHUB_URL_RE.match(url.strip())
    if not match or match.group("repo") in {".", ".."}:
        raise InvalidTargetError(
            f"Not a GitHub repository URL: {url!r} (expected https://github.com/<owner>/<repo>)"
        )
    return match.group("owner"), match.group("repo")


class GitHubLoader(Loader):
    """Loads ``https://github.com/<owner>/<repo>`` via a blobless clone.

    ``--filter=blob:none`` downloads full commit history cheaply; only the blobs needed
    for the checked-out tree are fetched.
    """

    def __init__(
        self,
        limits: LoaderLimits | None = None,
        filters: FilterConfig | None = None,
        *,
        allow_non_github_urls: bool = False,
    ) -> None:
        self.limits = limits or LoaderLimits()
        self.filters = filters or FilterConfig()
        self.allow_non_github_urls = allow_non_github_urls  # tests only (file:// fixtures)

    @staticmethod
    def can_handle(target: str) -> bool:
        return target.strip().lower().startswith("https://github.com/")

    def _validate(self, target: str, branch: str | None) -> str:
        if branch is not None and (not BRANCH_RE.match(branch) or branch.startswith("-")):
            raise InvalidTargetError(f"Invalid branch name: {branch!r}")
        if self.allow_non_github_urls:
            return target
        owner, repo = parse_github_url(target)
        return f"https://github.com/{owner}/{repo}.git"

    def _clone(self, url: str, dest: Path, branch: str | None) -> None:
        args = [
            "-c",
            "core.symlinks=false",
            "-c",
            "credential.helper=",
            "clone",
            "--quiet",
            "--filter=blob:none",
            "--single-branch",
            "--no-recurse-submodules",
        ]
        if branch:
            args += ["--branch", branch]
        args += ["--", url, str(dest)]
        try:
            run_git(args, timeout_s=self.limits.clone_timeout_s)
        except subprocess.TimeoutExpired as exc:
            raise LimitExceededError(
                f"Clone timed out after {self.limits.clone_timeout_s:.0f}s"
            ) from exc
        except GitCommandError as exc:
            raise LoaderError(f"Could not clone {url}: {exc}") from exc

    async def load(
        self,
        target: str,
        *,
        paths: Sequence[str] | None = None,
        branch: str | None = None,
    ) -> Workspace:
        if not git_available():
            raise LoaderError("git is not installed or not on PATH")
        url = self._validate(target, branch)
        tmp = Path(tempfile.mkdtemp(prefix="agents-lib-"))
        try:
            dest = tmp / "repo"
            await asyncio.to_thread(self._clone, url, dest, branch)
            size = await asyncio.to_thread(directory_size, dest)
            if size > self.limits.max_repo_size_bytes:
                raise LimitExceededError(
                    f"Repository is {size} bytes, above the {self.limits.max_repo_size_bytes} limit"
                )
            local = LocalLoader(self.limits, self.filters)
            ws = await asyncio.to_thread(local.load_sync, str(dest), paths=paths, source=target)
        except BaseException:
            force_rmtree(tmp)
            raise
        ws.add_cleanup(lambda: force_rmtree(tmp))
        return ws
