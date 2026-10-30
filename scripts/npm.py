"""Run npm using the portable workspace runtime, without changing system settings."""

import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
toolchain = json.loads((root / ".tools" / "toolchain.json").read_text())
node = Path(toolchain["node"])
environment = {**os.environ, "PATH": str(node.parent) + os.pathsep + os.environ.get("PATH", "")}
raise SystemExit(
    subprocess.run(
        [str(node.parent / "npm.cmd"), *sys.argv[1:]], cwd=root / "frontend", env=environment
    ).returncode
)
