"""Workspace abstraction produced by every loader."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path, PurePosixPath
from types import TracebackType

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from margin_core.errors import InvalidTargetError
from margin_core.logging import get_logger

logger = get_logger("loaders")


class FileInfo(BaseModel):
    """A file kept in the workspace."""

    path: str = Field(description="POSIX path relative to the workspace root.")
    size: int
    language: str | None = None
    is_generated: bool = False
    is_vendored: bool = False


class SkippedFile(BaseModel):
    """A file or directory excluded from the workspace, and why."""

    path: str
    reason: str


class GitCommit(BaseModel):
    """Commit metadata (no diffs)."""

    sha: str
    author_name: str
    author_email: str
    authored_at: datetime
    committer_name: str
    committer_email: str
    committed_at: datetime
    parents: list[str] = Field(default_factory=list)
    message: str

    @property
    def subject(self) -> str:
        return self.message.split("\n", 1)[0]


class GitInfo(BaseModel):
    """Access to a git repository's history, limited to the workspace being analysed.

    ``root`` is the repository's top level. ``prefix`` is the workspace root relative to it
    (empty when they are the same). ``pathspecs`` restrict history to the analysed files; an
    empty list means the whole repository.

    Every query here uses name-only history. In blobless clones, options such as
    ``--numstat``, ``--stat`` or ``-p`` would download every historical blob.
    """

    root: Path
    head: str | None = None
    branch: str | None = None
    prefix: str = ""
    pathspecs: list[str] = Field(default_factory=list)

    async def commits(self, max_count: int | None = None) -> list[GitCommit]:
        """Commits reachable from HEAD that touch the analysed files, newest first."""
        from margin_core.loaders.git import read_commits

        if self.head is None:
            return []
        return await read_commits(self.root, max_count=max_count, pathspecs=self.pathspecs)

    async def changed_files(self, max_count: int | None = None) -> dict[str, list[str]]:
        """Map of commit SHA to the workspace-relative files it changed (merges excluded)."""
        from margin_core.loaders.git import read_changed_files

        if self.head is None:
            return {}
        raw = await read_changed_files(self.root, pathspecs=self.pathspecs, max_count=max_count)
        result: dict[str, list[str]] = {}
        for sha, paths in raw:
            result[sha] = [rel for p in paths if (rel := self.to_workspace_path(p)) is not None]
        return result

    async def file_history(self, max_count: int | None = None) -> dict[str, list[str]]:
        """Map of workspace-relative path to SHAs of commits that changed it, newest first."""
        history: dict[str, list[str]] = {}
        for sha, paths in (await self.changed_files(max_count)).items():
            for path in paths:
                history.setdefault(path, []).append(sha)
        return history

    def to_workspace_path(self, repo_path: str) -> str | None:
        """Convert a repository-relative path to a workspace-relative one (None if outside)."""
        if not self.prefix:
            return repo_path
        lead = self.prefix + "/"
        return repo_path[len(lead) :] if repo_path.startswith(lead) else None


class LoaderLimits(BaseModel):
    """Safety limits. Exceeding a hard limit raises ``LimitExceededError``."""

    max_files: int = 10_000
    max_file_size_bytes: int = 1_000_000  # larger files are skipped, not fatal
    max_total_bytes: int = 100_000_000
    max_repo_size_bytes: int = 500_000_000
    clone_timeout_s: float = 180.0


class Workspace(BaseModel):
    """Files to analyse, independent of where they came from.

    Use as a context manager (sync or async) so temporary clones are cleaned up.
    """

    root: Path
    source: str
    files: list[FileInfo] = Field(default_factory=list)
    skipped: list[SkippedFile] = Field(default_factory=list)
    git: GitInfo | None = None
    warnings: list[str] = Field(default_factory=list)

    _cleanups: list[Callable[[], None]] = PrivateAttr(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def abs_path(self, file: FileInfo | str) -> Path:
        """Absolute path of ``file``; refuses paths that escape the workspace root."""
        rel = file.path if isinstance(file, FileInfo) else file
        root = self.root.resolve()
        full = (root / rel).resolve()
        if full != root and root not in full.parents:
            raise InvalidTargetError(f"Path escapes workspace root: {rel}")
        return full

    def read_text(self, file: FileInfo | str, max_bytes: int | None = None) -> str:
        """Read a file as UTF-8 (undecodable bytes replaced)."""
        with self.abs_path(file).open("rb") as fh:
            data = fh.read() if max_bytes is None else fh.read(max_bytes)
        return data.decode("utf-8", errors="replace")

    def exists(self, rel_path: str) -> bool:
        """Whether ``rel_path`` exists under the root, even inside filtered-out directories.

        Symlinks are not followed, and paths that try to leave the root return ``False``.
        """
        rel = PurePosixPath(rel_path.replace("\\", "/"))
        if rel.is_absolute() or ".." in rel.parts:
            return False
        return os.path.lexists(self.root / rel)

    def get_file(self, path: str) -> FileInfo | None:
        return next((f for f in self.files if f.path == path), None)

    def add_cleanup(self, fn: Callable[[], None]) -> None:
        self._cleanups.append(fn)

    def cleanup(self) -> None:
        while self._cleanups:
            fn = self._cleanups.pop()
            try:
                fn()
            except Exception:
                logger.warning("Workspace cleanup step failed", exc_info=True)

    def __enter__(self) -> Workspace:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.cleanup()

    async def __aenter__(self) -> Workspace:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.cleanup()


class Loader(ABC):
    """Turns a target (URL or path) into a :class:`Workspace`."""

    @staticmethod
    @abstractmethod
    def can_handle(target: str) -> bool:
        """Whether this loader understands ``target``."""

    @abstractmethod
    async def load(
        self,
        target: str,
        *,
        paths: Sequence[str] | None = None,
        branch: str | None = None,
    ) -> Workspace:
        """Load ``target``, optionally restricted to ``paths`` (relative to the root)."""
