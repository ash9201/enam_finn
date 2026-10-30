"""Read-only verification of real Cron execution, data completion and access."""

import json
import os

import httpx

from finn.config import ROOT, load_local_env, supabase_configuration
from finn.corpus import now
from finn.services import require_ok, supabase_client
from finn.store import open_store

load_local_env()
api = os.environ["FINN_DEPLOYED_API_URL"].rstrip("/")
_, secret, public = supabase_configuration()
with httpx.Client(timeout=120) as client:
    denied = [client.get(api + "/internal/source-sync").status_code]
    denied.append(client.post(api + "/internal/source-sync", json={"mode": "all"}).status_code)
    response = client.get(api + "/internal/source-sync", headers={"X-Finn-Sync-Key": secret})
    require_ok(response, "Deployed source-sync status")
    jobs = response.json()["jobs"]

with open_store() as store:
    schedules = store.rpc("finn_source_schedule_status", {})
    sources = store.rows("finn_sync_status")

with supabase_client(public) as anon:
    private_read = anon.get("rest/v1/finn_source_sync_job", params={"select": "id,token"})
    # Existing row is never changed even if an access-policy regression is found.
    private_write = anon.patch(
        "rest/v1/finn_source_sync_job", params={"id": "eq.1"}, json={"id": 1}
    )
    rpc_denied = anon.post("rest/v1/rpc/finn_source_schedule_status", json={}).status_code

access_ok = (
    denied == [403, 403]
    and private_read.status_code in [401, 403]
    and private_write.status_code in [401, 403]
    and rpc_denied in [401, 403]
    and schedules["job_table_rls"] is True
)
expected = {"finn-filings": "17,47 * * * *", "finn-eod-prices": "45 12 * * 1-5"}
scheduled = {row["name"]: row["schedule"] for row in schedules["schedules"] if row["active"]}
job_ok = bool(jobs and jobs[0]["origin"] == "supabase_cron" and jobs[0]["state"] == "completed")
sources_ok = len(sources) == 2 and all(
    row["state"] == "completed"
    and row["details"].get("execution_origin") == "supabase_cron"
    and row["details"].get("automation_verified") is True
    for row in sources
)
# Cron SQL success alone proves dispatch, not completion. Both are required.
dispatch_ok = any(row["status"] == "succeeded" for row in schedules["recent_runs"])
http_ok = any(row["status_code"] == 202 for row in schedules["http_responses"])
passed = access_ok and scheduled == expected and job_ok and sources_ok and dispatch_ok and http_ok
report = {
    "checked_at": now(),
    "api": api,
    "passed": passed,
    "access_ok": access_ok,
    "schedule_ok": scheduled == expected,
    "cron_dispatch_ok": dispatch_ok,
    "http_acceptance_ok": http_ok,
    "completion_ok": job_ok and sources_ok,
    "schedule_status": schedules,
    "jobs": jobs,
    "sources": sources,
}
destination = ROOT / "artifacts" / "release" / "supabase-cron-verification.json"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(
    json.dumps(
        {
            key: value
            for key, value in report.items()
            if key not in ["jobs", "sources", "schedule_status"]
        },
        indent=2,
    )
)
print("Report saved without credentials. HTTP 202 alone is not a completed refresh.")
raise SystemExit(0 if passed else 1)
