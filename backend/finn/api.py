from __future__ import annotations

import re
import uuid
import hmac
from typing import Literal
from concurrent.futures import ThreadPoolExecutor

import httpx

from fastapi import APIRouter, HTTPException, Query, Header
from pydantic import BaseModel, Field, field_validator

from finn import jobs
from finn.config import supabase_configuration
from finn.corpus import now
from finn.research import DEFAULT_QUESTION
from finn.services import DependencyError, MissingConfiguration
from finn.store import open_store
from finn.source_sync import run_sync, scheduled_mode

router = APIRouter()


def require_sync_operator(key: str | None):
    _, secret, _ = supabase_configuration()
    if not secret or not key or not hmac.compare_digest(secret, key):
        raise HTTPException(403, "Server operator access required.")


class SourceSyncRequest(BaseModel):
    mode: Literal["all", "filings", "prices"] = "all"
    trigger: Literal["operator", "cron"] = "operator"


@router.post("/internal/source-sync", status_code=202, include_in_schema=False)
def start_source_sync(
    request: SourceSyncRequest, x_finn_sync_key: str | None = Header(default=None)
):
    require_sync_operator(x_finn_sync_key)
    try:
        with open_store() as store:
            # Do not add a periodic refresh behind a long research backlog.
            jobs.expire_stale_jobs(store)
            active = store.rows(
                "finn_research_jobs", state="in.(queued,running)", select="id", limit=1
            )
            if active:
                raise HTTPException(
                    409, "Research is active; retry source sync on the next schedule."
                )
            token = str(uuid.uuid4())
            origin = "supabase_cron" if request.trigger == "cron" else "cloud_operator"
            mode = scheduled_mode(store, request.mode, request.trigger)
            acquired = store.rpc(
                "finn_acquire_source_sync",
                {
                    "p_token": token,
                    "p_mode": mode,
                    "p_origin": origin,
                },
            )
            if not acquired:
                raise HTTPException(409, "A source sync is already queued or running.")
        try:
            jobs.executor.submit(run_sync, token, mode, origin)
        except Exception as exc:
            with open_store() as store:
                store.patch(
                    "finn_source_sync_job",
                    {
                        "state": "failed",
                        "error": jobs.safe_error(exc),
                        "finished_at": now(),
                    },
                    id="eq.1",
                    token="eq." + token,
                )
            raise HTTPException(503, "The sync worker could not start. Retry later.") from None
        return {
            "job_id": token,
            "state": "queued",
            "mode": mode,
            "completion": "Check source-sync status; acceptance is not completion.",
        }
    except (DependencyError, MissingConfiguration) as exc:
        raise HTTPException(503, jobs.safe_error(exc)) from None


@router.get("/internal/source-sync", include_in_schema=False)
def source_sync_status(x_finn_sync_key: str | None = Header(default=None)):
    require_sync_operator(x_finn_sync_key)
    try:
        with open_store() as store:
            return {"jobs": store.rows("finn_source_sync_job", id="eq.1")}
    except (DependencyError, MissingConfiguration) as exc:
        raise HTTPException(503, jobs.safe_error(exc)) from None


@router.get("/internal/source-connectivity", include_in_schema=False)
def source_connectivity(x_finn_admin_key: str | None = Header(default=None)):
    """Fixed-source diagnostics, restricted to the server credential holder.

    No arbitrary URLs, document contents, credentials, or model calls are returned.
    IPv4 probing distinguishes an unavailable route from a source HTTP rejection.
    """
    _, secret, _ = supabase_configuration()
    if not secret or not x_finn_admin_key or not hmac.compare_digest(secret, x_finn_admin_key):
        raise HTTPException(403, "Server operator access required.")
    urls = {
        "nse_directory": "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
        "document_index": "https://www.screener.in/company/TCS/consolidated/",
        "model_host": "https://generativelanguage.googleapis.com/",
    }

    def probe(item):
        name, url, ipv4 = item
        transport = httpx.HTTPTransport(local_address="0.0.0.0") if ipv4 else None
        try:
            with httpx.Client(transport=transport, timeout=8, follow_redirects=True) as client:
                with client.stream("GET", url) as response:
                    return {
                        "source": name,
                        "mode": "ipv4" if ipv4 else "default",
                        "http_status": response.status_code,
                    }
        except (httpx.HTTPError, OSError) as exc:
            return {
                "source": name,
                "mode": "ipv4" if ipv4 else "default",
                "error_type": type(exc).__name__,
            }

    with ThreadPoolExecutor(max_workers=6) as pool:
        return {
            "checks": list(
                pool.map(
                    probe,
                    [(name, url, ipv4) for name, url in urls.items() for ipv4 in [False, True]],
                )
            )
        }


class ResearchRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=30, pattern=r"^[A-Z0-9&-]+$")
    question: str = Field(default=DEFAULT_QUESTION, min_length=8, max_length=600)
    refresh: bool = False

    @field_validator("symbol", mode="before")
    @classmethod
    def normalise_symbol(cls, value):
        return value.strip().upper().removesuffix(".NS") if isinstance(value, str) else value

    @field_validator("question")
    @classmethod
    def clean_question(cls, value):
        value = " ".join(value.split())
        if len(value) < 8:
            raise ValueError("Please ask a complete question.")
        return value


@router.get("/companies")
def companies(q: str = Query(default="", max_length=60)):
    clean = re.sub(r"[^A-Za-z0-9 &-]", "", q).strip()
    try:
        with open_store() as store:
            filters = (
                {"or": f"(symbol.ilike.*{clean}*,name.ilike.*{clean}*)"}
                if clean
                else {"portfolio": "eq.true"}
            )
            return {
                "companies": store.rows(
                    "finn_companies",
                    select="symbol,name,sector,portfolio,source_checked_at,coverage",
                    order="symbol",
                    limit=30,
                    **filters,
                )
            }
    except (DependencyError, MissingConfiguration) as exc:
        raise HTTPException(503, jobs.safe_error(exc)) from None


@router.get("/companies/{symbol}/research")
def prepared_research(symbol: str):
    symbol = symbol.upper().removesuffix(".NS")
    if not re.fullmatch(r"[A-Z0-9&-]{1,30}", symbol):
        raise HTTPException(422, "Invalid NSE symbol.")
    with open_store() as store:
        company = store.rows("finn_companies", symbol="eq." + symbol, limit=1)
        if not company or not company[0]["corpus_fingerprint"]:
            raise HTTPException(
                404, "No prepared research. Submit a question to discover this company."
            )
        cached = store.rows(
            "finn_research_cache",
            symbol="eq." + symbol,
            is_public="eq.true",
            corpus_fingerprint="eq." + company[0]["corpus_fingerprint"],
            order="created_at.desc",
            limit=1,
        )
        if not cached:
            raise HTTPException(404, "No published research for the current documents.")
        return {**cached[0]["result"], "cached": True, "cache_created_at": cached[0]["created_at"]}


@router.post("/research", status_code=202)
def start_research(request: ResearchRequest):
    try:
        with open_store() as store:
            security = store.rpc("finn_research_security_status", {})
            if (
                len(security.get("rls", {})) != 7
                or not all(security["rls"].values())
                or security.get("anon_bypasses_rls")
                or security.get("anon_private_select")
                or security.get("anon_cache_write")
            ):
                raise HTTPException(
                    503, "Research access policies need repair before processing can begin."
                )
            jobs.expire_stale_jobs(store)
            active = store.rows(
                "finn_research_jobs",
                state="in.(queued,running)",
                select="id,symbol,question,refresh",
                limit=3,
            )
            for job in active:
                if (job["symbol"], job["question"], job["refresh"]) == (
                    request.symbol,
                    request.question,
                    request.refresh,
                ):
                    return {"job_id": job["id"], "state": "queued"}
            if len(active) >= 3:
                raise HTTPException(429, "Research is busy. Please retry shortly.")
            job_id = str(uuid.uuid4())
            store.insert(
                "finn_research_jobs",
                {
                    "id": job_id,
                    "symbol": request.symbol,
                    "question": request.question,
                    "refresh": request.refresh,
                    "updated_at": now(),
                    "result": {"_worker": jobs.INSTANCE_ID, "_service": jobs.SERVICE_SCOPE},
                },
            )
        jobs.submit(job_id)
        return {"job_id": job_id, "state": "queued"}
    except (DependencyError, MissingConfiguration) as exc:
        raise HTTPException(503, jobs.safe_error(exc)) from None


@router.get("/jobs/{job_id}")
def job_status(job_id: uuid.UUID):
    with open_store() as store:
        jobs.expire_stale_jobs(store)
        result = store.rows(
            "finn_research_jobs",
            id="eq." + str(job_id),
            select="id,symbol,state,stage,error,result,created_at,updated_at",
            limit=1,
        )
        if not result:
            raise HTTPException(404, "Research request not found.")
        return result[0]
