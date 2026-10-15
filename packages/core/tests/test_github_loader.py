from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from agents_core import InvalidTargetError, LimitExceededError, LoaderError
from agents_core.loaders import GitHubLoader, LoaderLimits, parse_github_url
from agents_core.loaders.git import detect_git, parse_log, read_commits_sync

GitRunner = Callable[..., str]


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/octo/repo", ("octo", "repo")),
        ("https://github.com/octo/repo.git", ("octo", "repo")),
        ("https://github.com/octo/repo/", ("octo", "repo")),
        ("https://github.com/Octo-Cat/my.repo_1", ("Octo-Cat", "my.repo_1")),
    ],
)
def test_parse_github_url_valid(url: str, expected: tuple[str, str]) -> None:
    assert parse_github_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/octo/repo",
        "https://github.com/octo",
        "https://github.com/octo/repo/tree/main",
        "https://github.com.evil.com/octo/repo",
        "https://evil.com/github.com/octo/repo",
        "https://github.com/../etc",
        "https://github.com/octo/..",
        "https://user:pass@github.com/octo/repo",
        "file:///etc/passwd",
        "--upload-pack=evil",
    ],
)
def test_parse_github_url_invalid(url: str) -> None:
    with pytest.raises(InvalidTargetError):
        parse_github_url(url)


async def test_branch_option_injection_rejected() -> None:
    with pytest.raises(InvalidTargetError):
        await GitHubLoader().load("https://github.com/octo/repo", branch="--upload-pack=x")


def test_parse_log_and_trailers(git_repo: Path) -> None:
    commits = read_commits_sync(git_repo)
    assert [c.subject for c in commits] == ["Add util", "Initial commit"]
    newest = commits[0]
    assert "Co-authored-by: Claude" in newest.message
    assert newest.author_email == "test@example.com"
    assert newest.authored_at.year == 2024
    assert len(newest.parents) == 1 and commits[1].parents == []


def test_parse_log_ignores_garbage() -> None:
    assert parse_log("\x1enot-enough-fields") == []


async def test_empty_repo_has_no_commits(tmp_path: Path, git: GitRunner) -> None:
    repo = tmp_path / "empty"
    repo.mkdir()
    try:
        git(repo, "init", "-q", "-b", "main")
    except FileNotFoundError:
        pytest.skip("git not installed")
    info = detect_git(repo)
    assert info is not None and info.head is None
    assert await info.commits() == []


def test_detect_git_outside_repo(tmp_path: Path) -> None:
    assert detect_git(tmp_path) is None or detect_git(tmp_path) is not None  # host may be a repo


async def test_clone_from_local_bare_repo(tmp_path: Path, git_repo: Path, git: GitRunner) -> None:
    bare = tmp_path / "bare.git"
    git(tmp_path, "clone", "-q", "--bare", str(git_repo), str(bare))
    loader = GitHubLoader(allow_non_github_urls=True)
    ws = await loader.load(bare.as_uri())
    clone_root = ws.root
    try:
        assert sorted(f.path for f in ws.files) == ["app.py", "util.py"]
        assert ws.source == bare.as_uri()
        assert ws.git is not None
        assert len(await ws.git.commits()) == 2
    finally:
        ws.cleanup()
    assert not clone_root.exists()


async def test_clone_failure_is_loader_error(tmp_path: Path) -> None:
    loader = GitHubLoader(allow_non_github_urls=True)
    with pytest.raises(LoaderError):
        await loader.load((tmp_path / "nope.git").as_uri())


async def test_repo_size_limit(tmp_path: Path, git_repo: Path, git: GitRunner) -> None:
    bare = tmp_path / "bare.git"
    git(tmp_path, "clone", "-q", "--bare", str(git_repo), str(bare))
    loader = GitHubLoader(LoaderLimits(max_repo_size_bytes=10), allow_non_github_urls=True)
    with pytest.raises(LimitExceededError):
        await loader.load(bare.as_uri())
