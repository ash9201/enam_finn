"""Generic company corpus ingestion, versioned by primary-document content hashes."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
import uuid
import httpx

from finn.documents import extract_document
from finn.retrieval import CHUNK_VERSION, chunk_pages
from finn.sources import discover_documents, fetch_pdf, public_client, resolve_company


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ingest_document(
    store, client, company: dict, document: dict, *, progress=lambda stage: None
) -> dict:
    progress("download")
    try:
        data, final_url = fetch_pdf(client, document["source_url"])
    except (httpx.TransportError, OSError):
        raise ValueError(
            f"The original {document['kind'].replace('_', ' ')} PDF could not be reached from this server. No other content was substituted."
        ) from None
    digest = hashlib.sha256(data).hexdigest()
    document_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"finn:{company['symbol']}:{document['kind']}:{digest}")
    )
    existing = store.rows("finn_documents", id="eq." + document_id, limit=1)
    if (
        existing
        and existing[0]["state"] == "ready"
        and existing[0]["extraction_notes"].get("chunk_version") == CHUNK_VERSION
    ):
        store.patch("finn_documents", {"fetched_at": now()}, id="eq." + document_id)
        return {**existing[0], "reused_extraction": True}
    fetched_at = now()
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    extracted = extract_document(
        data, {**document, "final_url": final_url, "fetched_at": fetched_at}, progress=progress
    )
    progress("saving")
    storage_path = f"sources/{company['symbol']}/{digest}.pdf"
    store.put_pdf(storage_path, data)
    record = {
        "id": document_id,
        "symbol": company["symbol"],
        "kind": document["kind"],
        "sha256": digest,
        "source_url": document["source_url"],
        "final_url": final_url,
        "discovery_url": document["discovery_url"],
        "discovery_label": document["discovery_label"],
        "published_at": document.get("published_at"),
        "reporting_period": document.get("reporting_period"),
        "fetched_at": fetched_at,
        "extracted_at": extracted["extracted_at"],
        "page_count": extracted["page_count"],
        "storage_path": storage_path,
        "table_candidates": extracted["tables"],
        "state": "extracting",
        "extraction_notes": {
            "table_coverage": extracted["table_coverage"],
            "table_pages_checked": extracted["table_pages_checked"],
            "warnings": extracted["table_extraction_warnings"],
            "financial_comparisons_enabled": False,
            "chunk_version": CHUNK_VERSION,
            "text_extractor": extracted.get("text_extractor", "pypdf"),
        },
    }
    store.upsert("finn_documents", [record])
    store.upsert(
        "finn_document_pages",
        [
            {
                "document_id": document_id,
                "pdf_page": page["pdf_page"],
                "layout_text": page["text"],
                "metadata": {**page["metadata_candidates"], "reading_text": page["reading_text"]},
            }
            for page in extracted["pages"]
        ],
        conflict="document_id,pdf_page",
        batch_size=40,
    )
    chunks = chunk_pages(document_id, extracted["pages"], extracted["tables"])
    if not chunks:
        raise ValueError("No usable evidence chunks were extracted; the corpus was not published.")
    store.delete("finn_research_chunks", document_id="eq." + document_id)
    store.upsert("finn_research_chunks", chunks)
    store.patch("finn_documents", {"state": "ready"}, id="eq." + document_id)
    return {**record, "state": "ready", "chunks": len(chunks), "reused_extraction": False}


def ensure_corpus(store, symbol: str, *, refresh=False, progress=lambda stage: None) -> dict:
    existing = store.rows("finn_companies", symbol="eq." + symbol, limit=1)
    if existing and existing[0]["manifest"] and existing[0]["source_checked_at"] and not refresh:
        checked = datetime.fromisoformat(existing[0]["source_checked_at"])
        documents = store.rows(
            "finn_documents",
            id="in.(" + ",".join(existing[0]["manifest"]) + ")",
            select="id,state,extraction_notes",
        )
        current_index = len(documents) == len(existing[0]["manifest"]) and all(
            doc["state"] == "ready"
            and doc["extraction_notes"].get("chunk_version") == CHUNK_VERSION
            for doc in documents
        )
        if current_index and (datetime.now(timezone.utc) - checked).total_seconds() < 86400:
            return {**existing[0], "reused_corpus": True}
    progress("discovery")
    with public_client() as client:
        company = resolve_company(client, symbol)
        previous = existing[0] if existing else {}
        store.upsert(
            "finn_companies",
            [
                {
                    "symbol": company["symbol"],
                    "name": company["name"],
                    "isin": company["isin"],
                    "portfolio": previous.get("portfolio", False),
                    "sector": previous.get("sector"),
                    "manifest": previous.get("manifest", []),
                    "corpus_fingerprint": previous.get("corpus_fingerprint"),
                    "source_checked_at": previous.get("source_checked_at"),
                    "coverage": previous.get("coverage", {}),
                }
            ],
            conflict="symbol",
        )
        discovery = discover_documents(client, company)
        selected = (
            discovery["documents"]["annual_report"][:1] + discovery["documents"]["transcript"][:2]
        )
        documents = []
        for index, document in enumerate(selected):
            progress(f"extraction:{index + 1}/{len(selected)}")
            prefix = f"extraction:{index + 1}/{len(selected)}"
            documents.append(
                ingest_document(
                    store,
                    client,
                    company,
                    document,
                    progress=lambda phase, prefix=prefix: progress(f"{prefix}:{phase}"),
                )
            )
    # Activate the manifest only after every selected document is fully stored. A failed
    # refresh cannot replace the last complete corpus with partially ingested evidence.
    manifest = sorted({doc["id"] for doc in documents})
    fingerprint = hashlib.sha256(
        json.dumps([CHUNK_VERSION, sorted(doc["sha256"] for doc in documents)]).encode()
    ).hexdigest()
    coverage = {
        "annual_reports": sum(doc["kind"] == "annual_report" for doc in documents),
        "transcripts": sum(doc["kind"] == "transcript" for doc in documents),
        "target_annual_reports": 1,
        "target_transcripts": 2,
        "notes": [
            "Publication/reporting dates are unverified where null; discovery labels are shown separately.",
            "Financial table candidates are not approved for comparisons.",
        ],
    }
    updated = {
        "manifest": manifest,
        "corpus_fingerprint": fingerprint,
        "source_checked_at": now(),
        "coverage": coverage,
    }
    store.patch("finn_companies", updated, symbol="eq." + symbol)
    return {**company, **updated, "reused_corpus": False}
