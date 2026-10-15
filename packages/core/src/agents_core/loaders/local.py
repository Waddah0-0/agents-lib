"""Load a local directory (or a single file) into a :class:`Workspace`."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from agents_core.errors import InvalidTargetError, LimitExceededError
from agents_core.loaders.base import FileInfo, Loader, LoaderLimits, SkippedFile, Workspace
from agents_core.loaders.filters import (
    HEAD_BYTES,
    FilterConfig,
    classify_content,
    classify_path,
    detect_language,
    ignored_dir_reason,
)
from agents_core.loaders.git import detect_git


def _normalize_scopes(paths: Sequence[str] | None) -> list[str] | None:
    if not paths:
        return None
    scopes: list[str] = []
    for raw in paths:
        p = PurePosixPath(raw.replace("\\", "/"))
        if p.is_absolute() or ".." in p.parts:
            raise InvalidTargetError(
                f"Restricted paths must be relative and inside the root: {raw}"
            )
        text = str(p).strip("/")
        scopes.append("" if text == "." else text)
    return scopes


def _file_in_scope(rel: str, scopes: list[str] | None) -> bool:
    if scopes is None:
        return True
    return any(s == "" or rel == s or rel.startswith(s + "/") for s in scopes)


def _dir_in_scope(rel: str, scopes: list[str] | None) -> bool:
    """True if ``rel`` is inside a scope or is an ancestor of one (must descend)."""
    if scopes is None:
        return True
    return any(
        s == "" or rel == s or rel.startswith(s + "/") or s.startswith(rel + "/") for s in scopes
    )


class LocalLoader(Loader):
    """Walks a directory without following symlinks, applying filters and limits."""

    def __init__(
        self, limits: LoaderLimits | None = None, filters: FilterConfig | None = None
    ) -> None:
        self.limits = limits or LoaderLimits()
        self.filters = filters or FilterConfig()

    @staticmethod
    def can_handle(target: str) -> bool:
        return Path(target).expanduser().exists()

    async def load(
        self,
        target: str,
        *,
        paths: Sequence[str] | None = None,
        branch: str | None = None,
    ) -> Workspace:
        ws = await asyncio.to_thread(self.load_sync, target, paths=paths)
        if branch:
            ws.warnings.append("'branch' is ignored for local paths")
        return ws

    def load_sync(
        self, target: str, *, paths: Sequence[str] | None = None, source: str | None = None
    ) -> Workspace:
        root = Path(target).expanduser()
        if not root.exists():
            raise InvalidTargetError(f"Path does not exist: {target}")
        root = root.resolve()
        scopes = _normalize_scopes(paths)
        if root.is_file():
            scopes = [root.name]
            root = root.parent

        files: list[FileInfo] = []
        skipped: list[SkippedFile] = []
        total_bytes = 0

        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            current = Path(dirpath)
            rel_dir = current.relative_to(root).as_posix()
            rel_dir = "" if rel_dir == "." else rel_dir

            kept_dirs: list[str] = []
            for d in sorted(dirnames):
                rel = f"{rel_dir}/{d}" if rel_dir else d
                if (current / d).is_symlink():
                    skipped.append(SkippedFile(path=rel + "/", reason="symlink"))
                    continue
                reason = ignored_dir_reason(d, self.filters)
                if reason:
                    skipped.append(SkippedFile(path=rel + "/", reason=reason))
                    continue
                if _dir_in_scope(rel, scopes):
                    kept_dirs.append(d)
            dirnames[:] = kept_dirs

            for name in sorted(filenames):
                rel = f"{rel_dir}/{name}" if rel_dir else name
                if not _file_in_scope(rel, scopes):
                    continue
                full = current / name
                if full.is_symlink():
                    skipped.append(SkippedFile(path=rel, reason="symlink"))
                    continue
                decision = classify_path(rel, self.filters)
                if not decision.keep:
                    skipped.append(SkippedFile(path=rel, reason=decision.reason or "filtered"))
                    continue
                size = full.stat().st_size
                if size > self.limits.max_file_size_bytes:
                    skipped.append(SkippedFile(path=rel, reason="too_large"))
                    continue
                with full.open("rb") as fh:
                    head = fh.read(HEAD_BYTES)
                content = classify_content(rel, head, self.filters)
                if not content.keep:
                    skipped.append(SkippedFile(path=rel, reason=content.reason or "filtered"))
                    continue

                files.append(
                    FileInfo(
                        path=rel,
                        size=size,
                        language=detect_language(rel),
                        is_generated=decision.is_generated or content.is_generated,
                        is_vendored=decision.is_vendored,
                    )
                )
                total_bytes += size
                if len(files) > self.limits.max_files:
                    raise LimitExceededError(
                        f"More than {self.limits.max_files} files after filtering; "
                        "restrict the analysis with 'paths'"
                    )
                if total_bytes > self.limits.max_total_bytes:
                    raise LimitExceededError(
                        f"Workspace exceeds {self.limits.max_total_bytes} bytes after filtering"
                    )

        return Workspace(
            root=root,
            source=source or str(Path(target).expanduser().resolve()),
            files=files,
            skipped=skipped,
            git=detect_git(root),
        )
