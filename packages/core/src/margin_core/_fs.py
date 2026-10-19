"""Filesystem helpers."""

from __future__ import annotations

import os
import shutil
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _make_writable_and_retry(func: Callable[..., Any], path: str, _exc: object) -> None:
    os.chmod(path, stat.S_IWRITE)
    func(path)


def force_rmtree(path: Path) -> None:
    """Remove a directory tree, including read-only files (e.g. git objects on Windows)."""
    if not path.exists():
        return
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_make_writable_and_retry)
    else:
        shutil.rmtree(path, onerror=_make_writable_and_retry)


def directory_size(path: Path) -> int:
    """Total size in bytes of regular files under ``path`` (symlinks not followed)."""
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path, followlinks=False):
        for name in filenames:
            full = os.path.join(dirpath, name)
            if not os.path.islink(full):
                total += os.path.getsize(full)
    return total
