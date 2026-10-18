"""Run mypy on each workspace package separately.

One mypy run over the whole repo fails as soon as two packages contain files with the same
module name (every package has ``tests/conftest.py``, and agents commonly have
``tests/test_agent.py``). Checking each package on its own avoids those clashes while the
shared ``mypy_path`` still resolves imports between packages.

Usage: ``uv run python scripts/typecheck.py``
"""

from __future__ import annotations

import sys
from pathlib import Path

from mypy import api

ROOT = Path(__file__).resolve().parent.parent


def targets() -> list[list[str]]:
    groups = [
        [str(p)] for pattern in ("packages/*", "agents/*") for p in sorted(ROOT.glob(pattern))
    ]
    loose = [str(ROOT / "conftest.py"), str(ROOT / "scripts"), str(ROOT / "tests")]
    return [g for g in groups if Path(g[0]).is_dir()] + [loose]


def main() -> int:
    failed = 0
    for group in targets():
        stdout, stderr, status = api.run([*group, "--config-file", str(ROOT / "pyproject.toml")])
        name = ", ".join(Path(t).relative_to(ROOT).as_posix() for t in group)
        if status != 0:
            failed += 1
            print(f"FAIL {name}\n{stdout}{stderr}")
        else:
            print(f"ok   {name}: {stdout.strip().splitlines()[-1] if stdout.strip() else ''}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
