"""Server-resolved research anchors and bounded cross-document follow-ups."""

import re
import time
from collections import Counter
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from finn.documents import resolve_source_quote
from finn.retrieval import diversify, reciprocal_rank_fusion, retrieve_with_diagnostics

VERSION = "evidence-followup-v5"
DOCUMENT_FIELDS = (
    "id,kind,source_url,final_url,discovery_label,published_at,reporting_period,fetched_at"
)


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    research_id: UUID
    citation_id: UUID
    claim_index: int | None = Field(default=None, ge=0, le=6)
    intent: Literal["question", "repeated", "later", "perspective"] = "question"


def reference_dict(value):
    return EvidenceReference.model_validate(value).model_dump(mode="json", exclude_none=True)


def document_date(store, document):
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
    pages = store.rows(
        "finn_document_pages",
        document_id="eq." + document["id"],
        pdf_page="lte.4",
        select="pdf_page,layout_text,metadata",
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
    cache[document["id"]] = result
    store._call_dates = cache
    return result


def resolve_context(store, symbol, reference):
    ref = reference_dict(reference)
    records = store.rows(
        "finn_research_cache", id="eq." + ref["research_id"], symbol="eq." + symbol, limit=1
    )
    if not records or records[0]["result"].get("symbol") != symbol:
        raise ValueError(
            "This evidence is no longer available for this company. Open a current answer and select its evidence again."
        )
    answer = records[0]["result"]
    claims = list(answer.get("claims", []))
    comparison = answer.get("comparison") or {}
    claims += [comparison[key] for key in ["earlier", "later"] if comparison.get(key)]
    matches = [
        (index, c) for index, c in enumerate(claims) if c["citation"]["id"] == ref["citation_id"]
    ]
    if "claim_index" in ref:
        matches = [(index, c) for index, c in matches if index == ref["claim_index"]]
    if not matches:
        raise ValueError("The selected citation does not belong to this research answer.")
    if len(matches) != 1:
        raise ValueError(
            "This passage supports multiple claims. Reopen the claim to select its exact evidence context."
        )
    claim_index, claim = matches[0]
    citation = claim["citation"]
    documents = store.rows(
        "finn_documents",
        id="eq." + citation["document_id"],
        symbol="eq." + symbol,
        state="eq.ready",
        select=DOCUMENT_FIELDS,
        limit=1,
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
    quote = resolve_source_quote(citation["quote"], chunks[0]["body"]) if chunks else None
    if not quote:
        raise ValueError(
            "The original evidence has changed or is unavailable. Refresh the company research before following it up."
        )
    doc, chunk = documents[0], chunks[0]
    date = document_date(store, doc)
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
        **date,
    }
    context = {
        **ref,
        "claim_index": claim_index,
        "symbol": symbol,
        "claim": claim["statement"],
        "citation": {
            **citation,
            "quote": quote,
            "source_url": doc["source_url"],
            "document_url": doc["final_url"],
            **date,
        },
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
