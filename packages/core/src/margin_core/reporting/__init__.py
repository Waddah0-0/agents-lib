"""Report renderers for :class:`~margin_core.models.AgentResult`."""

from margin_core.reporting.json_report import to_json, write_json
from margin_core.reporting.markdown_report import to_markdown, write_markdown

__all__ = ["to_json", "to_markdown", "write_json", "write_markdown"]
