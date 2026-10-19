from __future__ import annotations

from pathlib import Path

from margin_core.models import AgentResult, Evidence, Finding, RunMetadata, TokenUsage
from margin_core.reporting import to_json, to_markdown, write_json, write_markdown


def _sample_result(status: str = "ok") -> AgentResult:
    return AgentResult(
        agent_id="test-agent",
        agent_version="0.1.0",
        status=status,  # type: ignore[arg-type]
        summary="A test run completed successfully.",
        findings=[
            Finding(
                title="Suspicious Pattern",
                severity_or_score=0.85,
                summary="Found high comment density.",
                evidence=[
                    Evidence(
                        kind="file",
                        location="src/main.py:10-20",
                        detail="Restating comments",
                        weight=0.5,
                    )
                ],
            )
        ],
        warnings=["Non-critical warning"],
        metadata=RunMetadata(
            duration_s=1.23,
            model="mock-model",
            usage=TokenUsage(llm_calls=2, input_tokens=100, output_tokens=50, cost_usd=0.005),
        ),
    )


def test_to_json_and_write_json(tmp_path: Path) -> None:
    res = _sample_result()
    json_str = to_json(res)
    assert '"agent_id": "test-agent"' in json_str
    assert '"Restating comments"' in json_str

    out_file = tmp_path / "report.json"
    written = write_json(res, out_file)
    assert written == out_file
    assert out_file.exists()
    assert AgentResult.model_validate_json(out_file.read_text(encoding="utf-8")) == res


def test_to_markdown_and_write_markdown(tmp_path: Path) -> None:
    res = _sample_result()
    md_str = to_markdown(res)
    assert "# test-agent report" in md_str
    assert "**Status:** ok" in md_str
    assert "### Suspicious Pattern (0.85)" in md_str
    assert "`src/main.py:10-20`" in md_str
    assert "_(weight +0.50)_" in md_str
    assert "## Warnings" in md_str
    assert "Non-critical warning" in md_str
    assert "| Duration | 1.23s |" in md_str
    assert "| Model | mock-model |" in md_str
    assert "| Estimated cost | $0.0050 |" in md_str

    out_file = tmp_path / "report.md"
    written = write_markdown(res, out_file)
    assert written == out_file
    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8") == md_str


def test_to_markdown_with_error() -> None:
    res = AgentResult(
        agent_id="test-agent",
        agent_version="0.1.0",
        status="error",
        summary="Run failed.",
        error="Detailed crash message",
    )
    md_str = to_markdown(res)
    assert "**Status:** error" in md_str
    assert "## Error" in md_str
    assert "Detailed crash message" in md_str
