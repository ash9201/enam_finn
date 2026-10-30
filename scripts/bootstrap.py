"""Install a workspace-local toolchain, verifying the official Node download hash.

Usage: python scripts/bootstrap.py
No system-wide Node installation or PATH/profile changes are made.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import urllib.request
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=90) as response:
        return response.read()


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Use Python 3.12 for this project.")
    if platform.system() != "Windows" or platform.machine().upper() not in {"AMD64", "X86_64"}:
        raise SystemExit(
            "This portable bootstrap is for Windows x64; use installed Node 24/Python 3.12 elsewhere."
        )

    tools = ROOT / ".tools"
    tools.mkdir(exist_ok=True)
    descriptor = tools / "toolchain.json"
    toolchain = json.loads(descriptor.read_text()) if descriptor.exists() else {}
    node = Path(toolchain.get("node", tools / "not-installed"))
    if not node.is_file():
        releases = json.loads(download("https://nodejs.org/dist/index.json"))
        release = next(
            item for item in releases if item["version"].startswith("v24.") and item["lts"]
        )
        version = release["version"]
        filename = f"node-{version}-win-x64.zip"
        checksums = download(f"https://nodejs.org/dist/{version}/SHASUMS256.txt").decode()
        expected = next(
            line.split()[0] for line in checksums.splitlines() if line.split()[-1] == filename
        )
        archive_bytes = download(f"https://nodejs.org/dist/{version}/{filename}")
        if hashlib.sha256(archive_bytes).hexdigest() != expected:
            raise SystemExit("Node archive SHA-256 did not match the official checksum.")
        archive = tools / filename
        archive.write_bytes(archive_bytes)
        with zipfile.ZipFile(archive) as zipped:
            for member in zipped.infolist():
                if not (tools / member.filename).resolve().is_relative_to(tools.resolve()):
                    raise SystemExit("Unexpected archive path.")
            zipped.extractall(tools)
        node = tools / f"node-{version}-win-x64" / "node.exe"
        descriptor.write_text(json.dumps({"node": str(node), "version": version}, indent=2))
        print(f"Installed workspace-local Node {version}; official SHA-256 verified.", flush=True)

    python = ROOT / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(ROOT / ".venv")
    subprocess.run([str(python), "-m", "pip", "install", "-e", ".[dev]"], cwd=ROOT, check=True)
    environment = {**os.environ, "PATH": str(node.parent) + os.pathsep + os.environ.get("PATH", "")}
    subprocess.run(
        [str(node.parent / "npm.cmd"), "install", "--no-fund", "--no-audit"],
        cwd=ROOT / "frontend",
        env=environment,
        check=True,
    )
    print("Toolchain ready. See README.md for local commands.", flush=True)


if __name__ == "__main__":
    main()
