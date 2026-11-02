"""Server-resolved research anchors and bounded cross-document follow-ups."""

import hashlib
import re
import time
from collections import Counter
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid5

import httpx
from pydantic import BaseModel, ConfigDict, Field

from finn.documents import resolve_source_quote
from finn.retrieval import diversify, reciprocal_rank_fusion, retrieve_with_diagnostics
from finn.services import DependencyError

VERSION = "evidence-followup-v5"
DOCUMENT_FIELDS = (
    "id,kind,source_url,final_url,discovery_label,published_at,reporting_period,fetched_at"
)


class EvidenceValidationError(ValueError):
    """A permanent citation validation failure, distinct from a storage outage."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    research_id: UUID
    citation_id: UUID
    claim_index: int | None = Field(default=None, ge=0, le=255)
    intent: Literal["question", "repeated", "later", "perspective"] = "question"


def reference_dict(value):
    return EvidenceReference.model_validate(value).model_dump(mode="json", exclude_none=True)


def document_date(store, document, *, pages=None):
    """An observed call-header date is distinct from a publication date or index label."""
    if document.get("published_at") and document["kind"] != "transcript":
        return {
            "document_date": document["published_at"],
            "document_date_basis": "Publication date",
        }
    if document["kind"] != "transcript":
        return {}
    cache = getattr(store, "_call_dates", {})
    if document["id"] in cache:
        return cache[document["id"]]
    pages = (
        pages
        if pages is not None
        else store.rows(
            "finn_document_pages",
            document_id="eq." + document["id"],
            pdf_page="lte.4",
            select="pdf_page,layout_text,metadata",
        )
    )
    found, locations = Counter(), {}
    for page in pages:
        text = page.get("metadata", {}).get("reading_text") or page.get("layout_text", "")
        # Header recurrence across pages avoids mistaking a cover-letter date for the call date.
        dates = set(
            re.findall(
                r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+20\d{2}\b",
                text[:650],
            )
        )
        page_dates = set()
        for raw in dates:
            try:
                value = datetime.strptime(raw.replace(",", ""), "%B %d %Y").date().isoformat()
            except ValueError:
                continue
            page_dates.add(value)
        for value in page_dates:
            found[value] += 1
            locations[value] = min(locations.get(value, page["pdf_page"]), page["pdf_page"])
    recurring = [date for date, count in found.items() if count >= 2]
    explicit = []
    for page in pages[:2]:
        text = " ".join(
            (page.get("metadata", {}).get("reading_text") or page.get("layout_text", "")).split()
        )
        if not re.search(r"transcript|earnings.*(?:call|meet)", text, re.I):
            continue
        for raw in re.findall(
            r"(?:held|conducted)\s+on\s+((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+20\d{2})",
            text,
            re.I,
        ):
            try:
                explicit.append(
                    (
                        datetime.strptime(raw.replace(",", "").title(), "%B %d %Y")
                        .date()
                        .isoformat(),
                        page["pdf_page"],
                    )
                )
            except ValueError:
                continue
    result = (
        {
            "document_date": recurring[0],
            "document_date_basis": "Repeated call header",
            "document_date_pdf_page": locations[recurring[0]],
        }
        if len(recurring) == 1
        else (
            {"document_date": document["published_at"], "document_date_basis": "Publication date"}
            if document.get("published_at")
            else {}
        )
    )
    if not result and len({d for d, _ in explicit}) == 1:
        result = {
            "document_date": explicit[0][0],
            "document_date_basis": "Call date stated in company filing",
            "document_date_pdf_page": explicit[0][1],
        }
    cache[document["id"]] = result
    store._call_dates = cache
    return result


def resolve_context(store, symbol, reference):
    ref = reference_dict(reference)
    records = store.rows(
        "finn_research_cache", id="eq." + ref["research_id"], symbol="eq." + symbol, limit=1
    )
    if not records or records[0]["result"].get("symbol") != symbol:
        raise EvidenceValidationError(
            "company_reference_invalid",
            "This evidence is no longer available for this company. Open a current answer and select its evidence again.",
        )
    answer = records[0]["result"]
    claims = list(answer.get("claims", []))
    comparison = answer.get("comparison") or {}
    claims += [comparison[key] for key in ["earlier", "later"] if comparison.get(key)]
    matches = [
        (index, c)
        for index, c in enumerate(claims)
        if any(s["id"] == ref["citation_id"] for s in c.get("citations", [c["citation"]]))
    ]
    if "claim_index" in ref:
        matches = [(index, c) for index, c in matches if index == ref["claim_index"]]
    if not matches:
        raise EvidenceValidationError(
            "citation_invalid", "The selected citation does not belong to this research answer."
        )
    if len(matches) != 1:
        raise EvidenceValidationError(
            "claim_ambiguous",
            "This passage supports multiple claims. Reopen the claim to select its exact evidence context.",
        )
    claim_index, claim = matches[0]
    citation = next(
        c for c in claim.get("citations", [claim["citation"]]) if c["id"] == ref["citation_id"]
    )
    try:
        UUID(citation.get("document_id", ""))
        if (
            type(citation.get("pdf_page")) is not int
            or citation["pdf_page"] < 1
            or not isinstance(citation.get("quote"), str)
            or not citation["quote"].strip()
        ):
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise EvidenceValidationError(
            "citation_invalid",
            "The stored citation has invalid document, page or passage information.",
        ) from None
    documents = store.rows(
        "finn_documents",
        id="eq." + citation["document_id"],
        symbol="eq." + symbol,
        state="eq.ready",
        select=DOCUMENT_FIELDS + ",sha256",
        limit=1,
    )
    if not documents:
        raise EvidenceValidationError(
            "document_missing",
            "The original evidence document is missing or is no longer ready. Open a current company answer.",
        )
    document_hash = (citation.get("metric_evidence") or {}).get("document_sha256")
    if document_hash and document_hash != documents[0].get("sha256"):
        raise EvidenceValidationError(
            "source_version_mismatch",
            "The original evidence document version has changed. Select evidence from a current answer.",
        )
    if citation.get("kind") and citation["kind"] != documents[0]["kind"]:
        raise EvidenceValidationError(
            "source_mismatch", "The cited document type does not match the stored source."
        )
    chunks = (
        store.rows(
            "finn_research_chunks",
            id="eq." + ref["citation_id"],
            document_id="eq." + citation["document_id"],
            select="id,document_id,pdf_page,body,metadata",
            limit=1,
        )
        if documents
        else []
    )
    if documents and citation.get("evidence_scope") == "page":
        chunks = []  # A stale page hash must not fall back to an unrelated chunk.
        pages = store.rows(
            "finn_document_pages",
            document_id="eq." + citation["document_id"],
            pdf_page="eq." + str(citation["pdf_page"]),
            select="layout_text,metadata",
            limit=1,
        )
        if pages:
            text = " ".join(
                (
                    pages[0].get("metadata", {}).get("reading_text") or pages[0]["layout_text"]
                ).split()
            )
            digest = hashlib.sha256(text.encode()).hexdigest()
            expected = str(
                uuid5(
                    UUID(citation["document_id"]), f"page-evidence:{citation['pdf_page']}:{digest}"
                )
            )
            if expected == ref["citation_id"] and digest == citation.get("page_hash"):
                chunks = [
                    {
                        "id": expected,
                        "document_id": citation["document_id"],
                        "pdf_page": citation["pdf_page"],
                        "body": text,
                        "metadata": {"evidence_scope": "page", "page_hash": digest},
                    }
                ]
    if chunks and (
        chunks[0]["id"] != ref["citation_id"]
        or chunks[0]["document_id"] != citation["document_id"]
        or chunks[0]["pdf_page"] != citation["pdf_page"]
    ):
        raise EvidenceValidationError(
            "source_mismatch", "The cited PDF page does not match the original stored passage."
        )
    quote = resolve_source_quote(citation["quote"], chunks[0]["body"]) if chunks else None
    if not quote:
        raise EvidenceValidationError(
            "passage_mismatch",
            "The original evidence has changed or is unavailable. Refresh the company research before following it up.",
        )
    doc, chunk = documents[0], chunks[0]
    try:
        date = document_date(store, doc)
    except (DependencyError, httpx.HTTPError):
        # Optional chronology is not the already-verified passage itself.
        date = {}
    anchor = {
        **chunk,
        "chunk_id": chunk["id"],
        **{
            k: doc.get(k)
            for k in [
                "kind",
                "source_url",
                "discovery_label",
                "published_at",
                "reporting_period",
                "fetched_at",
            ]
        },
        "document_url": doc["final_url"],
        **{k: citation[k] for k in ["evidence_scope", "page_hash"] if citation.get(k)},
        **{k: citation[k] for k in ["source_identifiers", "context_pdf_page"] if citation.get(k)},
        **date,
    }
    context = {
        "verification": {"state": "verified", "scope": "stored_source"},
        **ref,
        "claim_index": claim_index,
        "symbol": symbol,
        "claim": claim["statement"],
        "citation": {
            **citation,
            "kind": doc["kind"],
            "quote": quote,
            "source_url": doc["source_url"],
            "document_url": doc["final_url"],
            **date,
        },
        **(
            {
                "financial_documents": (
                    answer.get("financial_results") or answer["financial_metrics"]
                )["document_ids"],
                "financial_source_checked_at": answer["source_checked_at"],
                "financial_context_policy": "quarter-context-v2",
            }
            if answer.get("financial_results") or answer.get("financial_metrics")
            else {}
        ),
    }
    return context, anchor


def retrieve_followup(store, symbol, question, context, anchor, profile):
    started = time.perf_counter()
    # User follow-up and anchor topic are separate queries; neither restricts document scope.
    topic = context["claim"][:420]
    scope = {"kinds": ["transcript"]} if context["intent"] == "repeated" else {}
    primary = retrieve_with_diagnostics(
        store, symbol, question + "\nRegarding: " + topic, profile=profile, **scope
    )
    related = retrieve_with_diagnostics(store, symbol, topic, profile=profile, **scope)
    searches = [primary, related]
    ranked = reciprocal_rank_fusion(primary["evidence"], related["evidence"])
    if context.get("financial_documents") and context["intent"] != "repeated":
        # A numerical anchor must not drown out a qualitative follow-up. Search
        # the actual question in management commentary separately, then fuse it.
        commentary = retrieve_with_diagnostics(
            store, symbol, question, kinds=["transcript"], profile=profile
        )
        searches.append(commentary)
        ranked = reciprocal_rank_fusion(commentary["evidence"], ranked)
        extra = store.rpc(
            "finn_results_keyword_search",
            {
                "p_symbol": symbol,
                "p_query": " OR ".join(re.findall(r"[A-Za-z]{3,}", question + " " + topic)[:45]),
                "p_document_ids": context["financial_documents"],
                "p_limit": 10,
            },
        )
        ranked = reciprocal_rank_fusion(ranked, extra)
    anchor_date = anchor.get("document_date", "")[:10]
    later_ids = []
    if context["intent"] == "later" and anchor_date:
        company = store.rows("finn_companies", symbol="eq." + symbol, select="manifest", limit=1)
        manifest = company[0]["manifest"] if company else []
        documents = (
            store.rows(
                "finn_documents",
                symbol="eq." + symbol,
                id="in.(" + ",".join(manifest) + ")",
                state="eq.ready",
                select=DOCUMENT_FIELDS,
            )
            if manifest
            else []
        )
        later_ids = [
            doc["id"]
            for doc in documents
            if document_date(store, doc).get("document_date", "")[:10] > anchor_date
        ]
        if later_ids:
            later = retrieve_with_diagnostics(
                store,
                symbol,
                question + "\nRegarding: " + topic,
                document_ids=later_ids,
                profile=profile,
            )
            searches.append(later)
            ranked = reciprocal_rank_fusion(later["evidence"], ranked)
    others = [r for r in ranked if r["document_id"] != anchor["document_id"]]
    if context["intent"] == "later":
        others = [r for r in others if r["document_id"] in later_ids]
    same = [
        r
        for r in ranked
        if r["document_id"] == anchor["document_id"] and r["chunk_id"] != anchor["chunk_id"]
    ]
    if context["intent"] == "later":
        same = []  # The anchor alone cannot establish a later observation.
    # Reserve space for other documents before returning to the anchor's document.
    selected = diversify([anchor] + others + same)
    ids = ",".join(sorted({row["document_id"] for row in selected}))
    documents = (
        store.rows(
            "finn_documents", id="in.(" + ids + ")", symbol="eq." + symbol, select=DOCUMENT_FIELDS
        )
        if ids
        else []
    )
    dates = {doc["id"]: document_date(store, doc) for doc in documents}
    for row in selected:
        row.update(dates.get(row["document_id"], {}))
    if context["intent"] == "repeated" and anchor_date:
        selected = [
            row
            for row in selected
            if row["document_id"] == anchor["document_id"]
            or row.get("document_date", "")[:10] != anchor_date
        ]
    fallback = next((s["fallback_reason"] for s in searches if s["fallback_reason"]), None)
    return {
        **primary,
        "evidence": selected,
        "mode": "hybrid" if any(s["mode"] == "hybrid" for s in searches) else "keyword",
        "fallback_reason": fallback,
        "semantic_error": next(
            (s.get("semantic_error") for s in searches if s.get("semantic_error")), None
        ),
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "other_document_count": len(
            {r["document_id"] for r in selected if r["document_id"] != anchor["document_id"]}
        ),
        "later_document_ids": later_ids,
        "chronology_available": bool(anchor_date),
    }
