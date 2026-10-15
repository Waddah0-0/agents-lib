"""Report renderers for :class:`~agents_core.models.AgentResult`."""

from agents_core.reporting.json_report import to_json, write_json
from agents_core.reporting.markdown_report import to_markdown, write_markdown

__all__ = ["to_json", "to_markdown", "write_json", "write_markdown"]
