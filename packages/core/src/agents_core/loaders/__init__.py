"""Loaders turn a target (GitHub URL or local path) into a :class:`Workspace`."""

from __future__ import annotations

from collections.abc import Sequence

from agents_core.errors import InvalidTargetError
from agents_core.loaders.base import (
    FileInfo,
    GitCommit,
    GitInfo,
    Loader,
    LoaderLimits,
    SkippedFile,
    Workspace,
)
from agents_core.loaders.filters import FilterConfig
from agents_core.loaders.github import GitHubLoader, parse_github_url
from agents_core.loaders.local import LocalLoader

__all__ = [
    "FileInfo",
    "FilterConfig",
    "GitCommit",
    "GitHubLoader",
    "GitInfo",
    "Loader",
    "LoaderLimits",
    "LocalLoader",
    "SkippedFile",
    "Workspace",
    "load_workspace",
    "parse_github_url",
]


async def load_workspace(
    target: str,
    *,
    paths: Sequence[str] | None = None,
    branch: str | None = None,
    limits: LoaderLimits | None = None,
    filters: FilterConfig | None = None,
) -> Workspace:
    """Pick the right loader for ``target`` and load it."""
    stripped = target.strip()
    if GitHubLoader.can_handle(stripped):
        return await GitHubLoader(limits, filters).load(stripped, paths=paths, branch=branch)
    if "://" in stripped or stripped.startswith("git@"):
        raise InvalidTargetError(
            f"Unsupported URL {target!r}: only https://github.com/<owner>/<repo> is allowed"
        )
    return await LocalLoader(limits, filters).load(stripped, paths=paths, branch=branch)
