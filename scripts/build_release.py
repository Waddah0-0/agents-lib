"""Build every publishable package into dist/ and check the result before it goes to PyPI.

Usage::

    uv run python scripts/build_release.py              # build UI + packages, then verify
    uv run python scripts/build_release.py --skip-ui    # reuse an existing ui/dist

Steps:

1. build the web UI (same-address API) and copy it into margin-api, so
   ``pip install margin-api`` serves the whole app;
2. build a wheel and an sdist for every workspace member, except those marked
   ``Private :: Do Not Upload`` (the echo fixture);
3. check them: metadata (``twine check``), the bundled UI, ``py.typed``, and that every
   ``margin-*`` dependency range admits the version being released;
4. install the wheels into a fresh virtual environment and run them: ``margin list`` finds
   the agents, and ``margin-api`` serves the UI and the API.

Exits non-zero on any problem. The release workflow runs exactly this before publishing.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement
from packaging.version import Version

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
UI = ROOT / "ui"
BUNDLED_UI = ROOT / "packages" / "api" / "src" / "margin_api" / "ui"
PRIVATE = "Private :: Do Not Upload"


def run(
    cmd: list[str],
    *,
    cwd: Path | str | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(
        cmd, check=True, text=True, cwd=cwd, env=env, capture_output=capture_output
    )


Member = dict[str, Any]


def publishable() -> list[Member]:
    """Workspace members that may be uploaded, with their parsed metadata."""
    members = []
    for pyproject in sorted(
        [*ROOT.glob("packages/*/pyproject.toml"), *ROOT.glob("agents/*/pyproject.toml")]
    ):
        project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
        if PRIVATE in project.get("classifiers", []):
            continue
        members.append({**project, "dir": pyproject.parent})
    return members


def build_ui() -> None:
    npm = "npm.cmd" if os.name == "nt" else "npm"
    env = {**os.environ, "VITE_API_URL": ""}  # the API serves the UI: same address
    run([npm, "run", "build"], cwd=UI, env=env)
    shutil.rmtree(BUNDLED_UI, ignore_errors=True)
    shutil.copytree(UI / "dist", BUNDLED_UI)


def build(members: list[Member]) -> None:
    shutil.rmtree(DIST, ignore_errors=True)
    for m in members:
        run(["uv", "build", "--package", str(m["name"]), "--out-dir", str(DIST)], cwd=ROOT)


def check(members: list[Member]) -> list[str]:
    problems: list[str] = []
    versions = {str(m["name"]): Version(str(m["version"])) for m in members}
    for m in members:
        name, version = str(m["name"]), str(m["version"])
        wheel = next(DIST.glob(f"{name.replace('-', '_')}-{version}-*.whl"), None)
        if wheel is None:
            problems.append(f"{name}: no wheel for {version}")
            continue
        files = zipfile.ZipFile(wheel).namelist()
        if not any(f.endswith("/py.typed") for f in files):
            problems.append(f"{name}: no py.typed in the wheel")
        if not any(f.endswith("licenses/LICENSE") for f in files):
            problems.append(f"{name}: no LICENSE in the wheel metadata")
        if name == "margin-api" and "margin_api/ui/index.html" not in files:
            problems.append("margin-api: the web UI is not bundled")
        for dep in m.get("dependencies", []):
            req = Requirement(str(dep))
            if req.name in versions and versions[req.name] not in req.specifier:
                problems.append(f"{name}: requires {req}, but {req.name} is {versions[req.name]}")
    packages = sorted([*DIST.glob("*.whl"), *DIST.glob("*.tar.gz")])
    run(["uvx", "twine", "check", "--strict", *map(str, packages)])
    return problems


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def smoke_test() -> list[str]:
    """Install the wheels into a fresh environment and use them like a user would."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        venv = Path(tmp) / "venv"
        run(["uv", "venv", str(venv), "--python", "3.12", "--quiet"])
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        bin_dir = python.parent
        run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--quiet",
                *map(str, DIST.glob("*.whl")),
            ]
        )

        env = {
            **os.environ,
            "MARGIN_ENV_FILE": "",
            "MARGIN_CONFIG_FILE": "",
            "MARGIN_API_UI_DIR": "",
        }
        env.pop("VIRTUAL_ENV", None)
        listed = run(
            [str(bin_dir / "margin"), "list", "--json"], capture_output=True, env=env, cwd=tmp
        )
        ids = {a["id"] for a in json.loads(listed.stdout)["agents"]}
        if "ai-code-detector" not in ids:
            problems.append(f"margin list found {sorted(ids)}, not the detector")

        port = free_port()
        server = subprocess.Popen(
            [str(bin_dir / "margin-api")], env={**env, "MARGIN_API_PORT": str(port)}, cwd=tmp
        )
        try:
            base = f"http://127.0.0.1:{port}"
            for _ in range(60):
                try:
                    urllib.request.urlopen(f"{base}/health", timeout=1)
                    break
                except OSError:
                    time.sleep(0.5)
            page = urllib.request.Request(f"{base}/runs/x", headers={"accept": "text/html"})
            if b"<title>margin</title>" not in urllib.request.urlopen(page, timeout=5).read():
                problems.append("margin-api did not serve the bundled UI")
            agents = json.loads(urllib.request.urlopen(f"{base}/agents", timeout=5).read())
            if not any(a["id"] == "ai-code-detector" for a in agents["agents"]):
                problems.append("margin-api does not list the detector")
        except OSError as exc:
            problems.append(f"margin-api smoke test failed: {exc}")
        finally:
            server.terminate()
            server.wait(timeout=10)
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--skip-ui", action="store_true", help="reuse the UI already in ui/dist")
    args = parser.parse_args(argv)
    members = publishable()
    print("Publishing:", ", ".join(f"{m['name']} {m['version']}" for m in members))
    if args.skip_ui:
        shutil.rmtree(BUNDLED_UI, ignore_errors=True)
        shutil.copytree(UI / "dist", BUNDLED_UI)
    else:
        build_ui()
    try:
        build(members)
    finally:
        # the UI only belongs in the wheel: left in the source tree, every dev server and
        # test app would start serving it
        shutil.rmtree(BUNDLED_UI, ignore_errors=True)
    problems = check(members) + smoke_test()
    for p in problems:
        print("PROBLEM:", p)
    print("OK, ready to publish" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
