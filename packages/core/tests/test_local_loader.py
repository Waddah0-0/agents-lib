from __future__ import annotations

import os
from pathlib import Path

import pytest
from agents_core import InvalidTargetError, LimitExceededError
from agents_core.loaders import LoaderLimits, LocalLoader, load_workspace


def _write(root: Path, rel: str, content: str | bytes = "x = 1\n") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    _write(root, "src/app.py", "def main():\n    pass\n")
    _write(root, "src/util.ts", "export const a = 1;\n")
    _write(root, "README.md", "# Proj\n")
    _write(root, "package-lock.json", "{}")
    _write(root, "node_modules/lib/index.js", "module.exports = 1;\n")
    _write(root, "vendor/dep/dep.go", "package dep\n")
    _write(root, "assets/logo.png", b"\x89PNG\r\n")
    _write(root, "data/blob.dat", b"\x00\x01\x02")
    _write(root, "static/bundle.js", "var a=1;" * 600)
    _write(root, "gen/api_pb2.py", "# proto\n")
    _write(root, "big.txt", "a" * 6000)
    return root


async def test_local_loader_applies_filters(tree: Path) -> None:
    loader = LocalLoader(LoaderLimits(max_file_size_bytes=5000))
    ws = await loader.load(str(tree))
    kept = sorted(f.path for f in ws.files)
    assert kept == ["README.md", "src/app.py", "src/util.ts"]
    reasons = {s.path: s.reason for s in ws.skipped}
    assert reasons["package-lock.json"] == "lockfile"
    assert reasons["node_modules/"] == "ignored_dir"
    assert reasons["vendor/"] == "vendored"
    assert reasons["assets/logo.png"] == "binary"
    assert reasons["data/blob.dat"] == "binary"
    assert reasons["static/bundle.js"] == "minified"
    assert reasons["gen/api_pb2.py"] == "generated"
    assert reasons["big.txt"] == "too_large"
    assert ws.get_file("src/app.py") is not None
    assert ws.get_file("src/app.py").language == "python"  # type: ignore[union-attr]
    assert ws.read_text("src/app.py").startswith("def main")


async def test_paths_restriction(tree: Path) -> None:
    ws = await LocalLoader().load(str(tree), paths=["src/app.py", "README.md"])
    assert sorted(f.path for f in ws.files) == ["README.md", "src/app.py"]
    ws = await LocalLoader().load(str(tree), paths=["src"])
    assert sorted(f.path for f in ws.files) == ["src/app.py", "src/util.ts"]


@pytest.mark.parametrize("bad", ["../outside", "/etc/passwd", "src/../../x"])
async def test_paths_cannot_escape_root(tree: Path, bad: str) -> None:
    with pytest.raises(InvalidTargetError):
        await LocalLoader().load(str(tree), paths=[bad])


async def test_single_file_target(tree: Path) -> None:
    ws = await LocalLoader().load(str(tree / "src" / "app.py"))
    assert [f.path for f in ws.files] == ["app.py"]


async def test_missing_path() -> None:
    with pytest.raises(InvalidTargetError):
        await LocalLoader().load("definitely/not/here")


async def test_max_files_limit(tmp_path: Path) -> None:
    for i in range(5):
        _write(tmp_path, f"f{i}.py")
    with pytest.raises(LimitExceededError):
        await LocalLoader(LoaderLimits(max_files=3)).load(str(tmp_path))


async def test_total_bytes_limit(tmp_path: Path) -> None:
    for i in range(3):
        _write(tmp_path, f"f{i}.py", "x" * 100)
    with pytest.raises(LimitExceededError):
        await LocalLoader(LoaderLimits(max_total_bytes=250)).load(str(tmp_path))


async def test_symlinks_are_not_followed(tmp_path: Path) -> None:
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    root = tmp_path / "proj"
    _write(root, "a.py")
    try:
        os.symlink(outside, root / "link.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not permitted on this system")
    ws = await LocalLoader().load(str(root))
    assert [f.path for f in ws.files] == ["a.py"]
    assert {s.path: s.reason for s in ws.skipped}["link.txt"] == "symlink"


async def test_workspace_abs_path_guard(tree: Path) -> None:
    ws = await LocalLoader().load(str(tree))
    with pytest.raises(InvalidTargetError):
        ws.abs_path("../escape.txt")


async def test_branch_warning_for_local(tree: Path) -> None:
    ws = await LocalLoader().load(str(tree), branch="main")
    assert ws.warnings


async def test_git_detected(git_repo: Path) -> None:
    ws = await LocalLoader().load(str(git_repo))
    assert ws.git is not None
    assert ws.git.branch == "main"
    commits = await ws.git.commits()
    assert len(commits) == 2


async def test_load_workspace_rejects_other_urls() -> None:
    for url in ["http://github.com/a/b", "https://gitlab.com/a/b", "git@github.com:a/b.git"]:
        with pytest.raises(InvalidTargetError):
            await load_workspace(url)


async def test_load_workspace_local(tree: Path) -> None:
    async with await load_workspace(str(tree)) as ws:
        assert ws.files
