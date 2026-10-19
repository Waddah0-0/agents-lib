"""The GitHub API size check that runs before cloning."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from margin_core import AgentInput, AgentResult, BaseAgent, RunContext
from margin_core.errors import InvalidTargetError, LimitExceededError
from margin_core.loaders import GitHubLoader, LoaderLimits
from pydantic import BaseModel


def _loader(response: httpx.Response | Exception, **kwargs: object) -> GitHubLoader:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/octo/repo"
        if isinstance(response, Exception):
            raise response
        return response

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return GitHubLoader(LoaderLimits(max_repo_size_bytes=1_000_000), http_client=http, **kwargs)  # type: ignore[arg-type]


async def test_small_repo_passes() -> None:
    assert (
        await _loader(httpx.Response(200, json={"size": 10})).check_remote_size("octo", "repo")
        is None
    )


async def test_large_repo_refused_before_cloning(monkeypatch: pytest.MonkeyPatch) -> None:
    loader = _loader(httpx.Response(200, json={"size": 5_000}))  # 5 MB > 1 MB

    def no_clone(*_: object) -> None:
        raise AssertionError("must not clone")

    monkeypatch.setattr(loader, "_clone", no_clone)
    with pytest.raises(LimitExceededError, match="according to GitHub"):
        await loader.load("https://github.com/octo/repo")


async def test_missing_or_private_repo() -> None:
    with pytest.raises(InvalidTargetError, match="private"):
        await _loader(httpx.Response(404)).check_remote_size("octo", "repo")


@pytest.mark.parametrize(
    "response",
    [httpx.Response(403, json={"message": "rate limited"}), httpx.ConnectError("offline")],
)
async def test_api_problems_become_warnings(response: httpx.Response | Exception) -> None:
    warning = await _loader(response).check_remote_size("octo", "repo")
    assert warning is not None and "Could not check the repository size" in warning


async def test_token_is_sent_only_to_the_api() -> None:
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("authorization"))
        return httpx.Response(200, json={"size": 1})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    loader = GitHubLoader(http_client=http, github_token="tok")
    await loader.check_remote_size("octo", "repo")
    assert seen == ["Bearer tok"]


class In(AgentInput):
    target: str


class Out(BaseModel):
    files: int


class Lister(BaseAgent):
    id = "lister"
    name = "Lister"
    description = "Counts files"
    version = "0.0.1"
    InputModel = In
    OutputModel = Out
    primary_input = "target"

    async def run(self, input: In, ctx: RunContext) -> AgentResult:
        async with await ctx.load_workspace(input.target, branch="main") as ws:
            return self.make_result(summary="ok", output=Out(files=len(ws.files)))


async def test_workspace_warnings_reach_the_result(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    events: list[str] = []
    result = await Lister().execute(
        {"target": str(tmp_path)}, RunContext(progress=lambda e: events.append(e.stage))
    )
    assert result.status == "ok" and result.data == {"files": 1}
    assert result.warnings == ["'branch' is ignored for local paths"]
    assert events == ["load"]


def test_token_comes_from_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text("GITHUB_TOKEN=from-dotenv\n", encoding="utf-8")
    monkeypatch.setenv("MARGIN_ENV_FILE", str(env))
    assert GitHubLoader().github_token == "from-dotenv"
    monkeypatch.setenv("GITHUB_TOKEN", "from-env")
    assert GitHubLoader().github_token == "from-env"  # real environment variables win
    monkeypatch.setenv("MARGIN_ENV_FILE", "")
    monkeypatch.delenv("GITHUB_TOKEN")
    assert GitHubLoader().github_token is None
