"""Write the API's OpenAPI schema to ui/openapi.json (or check it is up to date).

Usage::

    uv run python scripts/export_openapi.py          # write
    uv run python scripts/export_openapi.py --check  # CI: fail if the file is stale

The UI (phase 6) generates its typed client from this file, so it must match the code.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "ui" / "openapi.json"


def schema_text() -> str:
    from agents_api.app import create_app
    from agents_api.settings import ApiSettings
    from agents_core import AgentRegistry

    # The schema does not depend on which agents are installed: inputs are validated
    # against each agent's own schema at run time (GET /agents/{id} returns it).
    app = create_app(registry=AgentRegistry([]), settings=ApiSettings(), llm_factory=None)
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="fail if the file is out of date")
    args = parser.parse_args(argv)
    text = schema_text()
    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != text:
            print(f"{TARGET.relative_to(ROOT)} is out of date; run scripts/export_openapi.py")
            return 1
        print(f"{TARGET.relative_to(ROOT)} is up to date")
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(text, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
