"""Export only anonymously readable data as an explicitly dated offline demo snapshot."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from finn.config import load_local_env, supabase_configuration
from finn.services import require_ok, supabase_client

load_local_env()
_, _, public = supabase_configuration()
if not public:
    raise SystemExit("Configure the publishable key before exporting public demo data.")
tables = {}
with supabase_client(public) as client:
    for name in [
        "finn_companies",
        "finn_filings",
        "finn_price_snapshots",
        "finn_sync_status",
        "finn_research_cache",
    ]:
        params = {"select": "*", "limit": 1000}
        if name == "finn_research_cache":
            params.update(is_public="eq.true", order="created_at.desc")
        response = client.get("rest/v1/" + name, params=params)
        require_ok(response, "Public snapshot export")
        rows = response.json()
        if name == "finn_research_cache":
            latest = {}
            for row in rows:
                latest.setdefault((row["symbol"], row["question"]), row)
            rows = list(latest.values())
        tables[name] = rows
record = {
    "mode": "recorded_demo_snapshot",
    "exported_at": datetime.now(timezone.utc).isoformat(),
    "notice": "Recorded demo data. Live saved updates could not be loaded. Original source and session dates remain authoritative.",
    "tables": tables,
}
text = json.dumps(record, ensure_ascii=False, indent=2)
for name, value in os.environ.items():
    if (
        len(value) > 12
        and any(token in name for token in ["SECRET", "GEMINI_API_KEY", "GOOGLE_API_KEY"])
        and value in text
    ):
        raise SystemExit(
            "Snapshot contains a privileged value; export refused without printing it."
        )
target = Path(__file__).resolve().parents[1] / "frontend" / "public" / "recorded-snapshot.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(text, encoding="utf-8")
print(
    f"Exported public, dated snapshot: {len(text.encode())} bytes. No private source text, custom questions, or credentials exported."
)
