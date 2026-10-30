"""Check emitted assets for actual local secrets and common privileged key formats."""
from pathlib import Path
import os
import re
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env.local", override=False)
secrets = [value for name, value in os.environ.items() if len(value) > 12 and any(word in name for word in ["SECRET", "SERVICE_ROLE", "GEMINI_API_KEY", "GOOGLE_API_KEY"]) and not name.startswith("VITE_")]
files = [path for path in (ROOT / "frontend" / "dist").rglob("*") if path.is_file()]
if not files:
    raise SystemExit("Build frontend assets before scanning.")
for path in files:
    data = path.read_bytes()
    if any(value.encode() in data for value in secrets) or re.search(rb"sb_secret_[A-Za-z0-9_-]{12,}", data):
        print(f"FAILED: privileged credential found in {path.name}; value suppressed.")
        sys.exit(1)
print(f"PASS: {len(files)} built files scanned; no configured privileged credentials found.")
