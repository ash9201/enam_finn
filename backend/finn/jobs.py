"""Small persisted research jobs, executed serially to bound memory and API use."""

from __future__ import annotations

import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from finn.corpus import now
from finn.research import research_company
from finn.store import open_store
from finn.timing import tracing

executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="finn-research")
answer_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="finn-prepared")
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

        last_progress = ["", 0.0]
        partial = {**(job.get("result") or {}), "_progress": {"sources": []}}

        def progress(stage):
            phase = ":".join(stage.split(":")[:3]) if stage.startswith("extraction:") else stage
            if phase == last_progress[0] and time.monotonic() - last_progress[1] < 3:
                return
            last_progress[:] = [phase, time.monotonic()]
            store.patch(
                "finn_research_jobs",
                {"state": "running", "stage": stage, "updated_at": now()},
                id="eq." + job_id,
            )

        def source_ready(document):
            saved = partial["_progress"]["sources"]
            if not any(s["id"] == document["id"] for s in saved):
                saved.append(
                    {
                        "id": document["id"],
                        "kind": document["kind"],
                        "label": document["discovery_label"],
                        "source_url": document["source_url"],
                        "pages": document["page_count"],
                    }
                )
                store.patch(
                    "finn_research_jobs",
                    {"result": partial, "updated_at": now()},
                    id="eq." + job_id,
                )

        progress.source_ready = source_ready

        try:
            progress("corpus_check")
            request = (job.get("result") or {}).get("_request", {})
            extra = {}
            if request.get("context"):
                extra["context_reference"] = request["context"]
            if request.get("include_history"):
                extra["include_history"] = True
            queued = (
                datetime.now(timezone.utc) - datetime.fromisoformat(job.get("created_at") or now())
            ).total_seconds() * 1000
            with tracing(queue_ms=queued) as trace:
                result = research_company(
                    store,
                    job["symbol"],
                    job["question"],
                    refresh=job["refresh"],
                    progress=progress,
                    **extra,
                )
                result["timings"] = trace.summary()
            store.patch(
                "finn_research_jobs",
                {"state": "completed", "stage": "completed", "result": result, "updated_at": now()},
                id="eq." + job_id,
            )
            from finn import embeddings

            embeddings.schedule_backfill(job["symbol"])
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


def submit(job_id: str, *, prepared=False):
    # One acquisition worker bounds PDF memory. A separate I/O/model lane prevents
    # prepared-company questions waiting behind a long first-time download.
    (answer_executor if prepared else executor).submit(run_job, job_id)
