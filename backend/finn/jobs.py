"""Small persisted research jobs, executed serially to bound memory and API use."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
import uuid

from finn.corpus import now
from finn.research import research_company
from finn.store import open_store

executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="finn-research")
INSTANCE_ID = str(uuid.uuid4())
SERVICE_SCOPE = os.getenv("RENDER_SERVICE_ID") or ("local-" + os.getenv("FINN_ENV", "development"))


def safe_error(exc: Exception) -> str:
    text = str(exc)
    for name, value in os.environ.items():
        if (
            any(word in name for word in ["SECRET", "SERVICE_ROLE", "API_KEY", "TOKEN", "PASSWORD"])
            and len(value) > 8
        ):
            text = text.replace(value, "[REDACTED]")
    return text[:600] or "Research could not finish. Please retry."


def expire_stale_jobs(store):
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
    store.patch(
        "finn_research_jobs",
        {
            "state": "failed",
            "stage": "failed",
            "error": "Processing was interrupted. Please retry this research request.",
            "updated_at": now(),
        },
        state="in.(queued,running)",
        updated_at="lt." + cutoff,
    )
    # One API worker per service. Detect its interrupted jobs immediately after a
    # restart, while not taking ownership of a separate local/Render service's work.
    active = store.rows(
        "finn_research_jobs", state="in.(queued,running)", select="id,result", limit=50
    )
    for job in active:
        owner = job.get("result") or {}
        if owner.get("_service") == SERVICE_SCOPE and owner.get("_worker") not in [
            None,
            INSTANCE_ID,
        ]:
            store.patch(
                "finn_research_jobs",
                {
                    "state": "failed",
                    "stage": "failed",
                    "error": "The research service restarted. Any saved source documents will be reused; please retry.",
                    "updated_at": now(),
                },
                id="eq." + job["id"],
            )


def run_job(job_id: str):
    with open_store() as store:
        jobs = store.rows("finn_research_jobs", id="eq." + job_id, limit=1)
        if not jobs or jobs[0]["state"] != "queued":
            return
        job = jobs[0]

        def progress(stage):
            store.patch(
                "finn_research_jobs",
                {"state": "running", "stage": stage, "updated_at": now()},
                id="eq." + job_id,
            )

        try:
            progress("discovery")
            result = research_company(
                store, job["symbol"], job["question"], refresh=job["refresh"], progress=progress
            )
            store.patch(
                "finn_research_jobs",
                {"state": "completed", "stage": "completed", "result": result, "updated_at": now()},
                id="eq." + job_id,
            )
        except Exception as exc:
            store.patch(
                "finn_research_jobs",
                {
                    "state": "failed",
                    "stage": "failed",
                    "error": safe_error(exc),
                    "updated_at": now(),
                },
                id="eq." + job_id,
            )


def submit(job_id: str):
    executor.submit(run_job, job_id)
