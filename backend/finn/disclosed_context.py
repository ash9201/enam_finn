"""Conservative, direct current-quarter disclosures, not a causal earnings bridge."""

import hashlib
import re
import uuid
from copy import deepcopy

import httpx

from finn.documents import native_page_texts
from finn.financial_tables import parse_date
from finn.research import citation_from_source
from finn.retrieval import chunk_pages
from finn.services import DependencyError

VERSION = "quarter-disclosed-context-v2"
CATEGORIES = [
    (
        r"acquisition[- ]related|transaction costs",
        "The filing discloses acquisition or transaction-related costs for this quarter.",
    ),
    (
        r"settlement agreement.*(?:litigation|antitrust|court)|(?:litigation|antitrust|court).*settlement",
        "The filing discloses a litigation settlement for this quarter.",
    ),
]


def quarter_in_quote(quote, quarter):
    return any(
        parse_date(m.group(1)) == quarter
        for m in re.finditer(r"quarter\s+ended\s+(.{0,60})", quote, re.I)
    )


def preserve_missing_pages(store, document):
    if document["extraction_notes"].get("financial_native_pages_version") == 1:
        return
    native = native_page_texts(
        store.get_pdf(document["storage_path"], document["sha256"]), lambda stage: None
    )
    if len(native) > 200:
        return
    existing = {
        p["pdf_page"]
        for p in store.rows(
            "finn_document_pages", document_id="eq." + document["id"], select="pdf_page"
        )
    }
    pages = [
        {
            "pdf_page": i,
            "text": text,
            "reading_text": text,
            "metadata_candidates": {"financial_figures_validated": False},
        }
        for i, text in enumerate(native, 1)
        if i not in existing and text.strip()
    ]
    if pages:
        store.upsert(
            "finn_document_pages",
            [
                {
                    "document_id": document["id"],
                    "pdf_page": p["pdf_page"],
                    "layout_text": p["text"],
                    "metadata": {
                        "reading_text": p["reading_text"],
                        "financial_figures_validated": False,
                    },
                }
                for p in pages
            ],
            conflict="document_id,pdf_page",
        )
        chunks = chunk_pages(document["id"], pages, [])
        for chunk in chunks:
            chunk["metadata"]["contains_table_candidates"] = True
        store.upsert("finn_research_chunks", chunks)
    document["extraction_notes"] = {
        **document["extraction_notes"],
        "financial_native_pages_version": 1,
    }
    store.patch(
        "finn_documents",
        {"extraction_notes": document["extraction_notes"]},
        id="eq." + document["id"],
    )


def disclosed_paragraphs(text, quarter):
    flat = " ".join(text.split())
    starts = [0, *[m.start() for m in re.finditer(r"\s[a-z]\)\s|\s\d+\s+Exceptional\b", flat)]]
    for start, end in zip(starts, [*starts[1:], len(flat)]):
        paragraph = flat[start:end].strip()
        if len(paragraph) > 1800 or not quarter_in_quote(paragraph, quarter):
            continue
        for pattern, statement in CATEGORIES:
            if re.search(pattern, paragraph, re.I):
                yield statement, paragraph


def add_disclosed_context(store, result):
    data = result.get("financial_results") or {}
    if not result.get("claims") or not data.get("bases") or data.get("context_version") == VERSION:
        return result
    basis = "consolidated" if "consolidated" in data["bases"] else "standalone"
    quarter = data["periods"]["latest"]
    try:
        docs = store.rows("finn_documents", id="in.(" + ",".join(data["document_ids"]) + ")")
        claims = []
        chunks = []
        seen = set()
        for document in docs:
            preserve_missing_pages(store, document)
            pages = store.rows(
                "finn_document_pages",
                document_id="eq." + document["id"],
                order="pdf_page",
                select="pdf_page,layout_text,metadata",
            )
            for page in pages:
                anchors = [
                    c["citation"]
                    for c in result["claims"]
                    if c["citation"].get("financial_evidence", {}).get("period_end") == quarter
                    and c["citation"]["document_id"] == document["id"]
                    and c["citation"]["pdf_page"] <= page["pdf_page"]
                ]
                nearest = max((a["pdf_page"] for a in anchors), default=None)
                if nearest == page["pdf_page"] or {
                    a["financial_evidence"]["accounting_basis"]
                    for a in anchors
                    if a["pdf_page"] == nearest
                } != {basis}:
                    continue
                text = page["metadata"].get("reading_text") or page["layout_text"]
                for statement, quote in disclosed_paragraphs(text, quarter):
                    if statement in seen or len(claims) >= 2:
                        continue
                    digest = hashlib.sha256(quote.encode()).hexdigest()
                    cid = str(
                        uuid.uuid5(
                            uuid.UUID(document["id"]),
                            "disclosed-context:" + str(page["pdf_page"]) + ":" + digest,
                        )
                    )
                    source = {
                        **document,
                        "chunk_id": cid,
                        "pdf_page": page["pdf_page"],
                        "body": quote,
                        "metadata": {"contains_table_candidates": True},
                        "document_id": document["id"],
                        "document_url": document["final_url"],
                        "reporting_period": quarter,
                    }
                    claims.append(
                        {
                            "statement": statement.replace("The filing", f"The {basis} filing"),
                            "citation": citation_from_source(source, quote),
                        }
                    )
                    chunks.append(
                        {
                            "id": cid,
                            "document_id": document["id"],
                            "pdf_page": page["pdf_page"],
                            "ordinal": 30000 + len(claims),
                            "body": quote,
                            "metadata": source["metadata"],
                        }
                    )
                    seen.add(statement)
        if chunks:
            store.upsert("finn_research_chunks", chunks)
        result = deepcopy(result)
        indices = []
        for claim in claims:
            indices.append(len(result["claims"]))
            result["claims"].append(claim)
        result["financial_results"]["bases"][basis]["context_claim_indices"] = indices
        result["financial_results"]["context_version"] = VERSION
        return result
    except (DependencyError, httpx.HTTPError, ValueError, KeyError):
        return result
