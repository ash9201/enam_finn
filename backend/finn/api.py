from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from finn import jobs
from finn.corpus import now
from finn.research import DEFAULT_QUESTION
from finn.services import DependencyError, MissingConfiguration
from finn.store import open_store

router = APIRouter()


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
