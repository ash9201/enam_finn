"""Keyword retrieval now; stable metadata/evidence interfaces for later pgvector RRF."""

from __future__ import annotations

from collections import Counter
import re
import uuid

CHUNK_VERSION = "page-chunks-v2-reading-order"
STOP_WORDS = set(
    "what which who how when where why does do did is are was were the a an of for to in on and or about please explain tell me company its their main has have latest according report reports said say".split()
)
EXPANSIONS = {
    "business": ["business", "services", "products", "segments"],
    "segments": ["segments", "business", "services"],
    "guidance": ["guidance", "outlook", "expect", "growth"],
    "margins": ["margin", "profitability", "operating"],
    "cash": ["cash", "operating", "conversion"],
}


def keyword_query(question: str) -> str:
    tokens = [
        word.lower()
        for word in re.findall(r"[A-Za-z0-9]+", question)
        if len(word) > 1 and word.lower() not in STOP_WORDS
    ]
    expanded = [value for token in tokens for value in EXPANSIONS.get(token, [token])]
    return " OR ".join(dict.fromkeys(expanded))[:1600]


def chunk_pages(
    document_id: str, pages: list[dict], tables: list[dict], *, size=1800, overlap=240
) -> list[dict]:
    table_pages = {table["pdf_page"] for table in tables}
    result = []
    for page in pages:
        # Original layout text is retained separately; retrieval normalises whitespace.
        text = " ".join(page.get("reading_text", page["text"]).split())
        if len(text) < 70:
            continue
        start, ordinal = 0, 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                space = text.rfind(" ", start + size // 2, end)
                if space > start:
                    end = space
            body = text[start:end].strip()
            result.append(
                {
                    "id": str(
                        uuid.uuid5(
                            uuid.UUID(document_id), f"{CHUNK_VERSION}:{page['pdf_page']}:{ordinal}"
                        )
                    ),
                    "document_id": document_id,
                    "pdf_page": page["pdf_page"],
                    "ordinal": ordinal,
                    "body": body,
                    "metadata": {
                        **page["metadata_candidates"],
                        "contains_table_candidates": page["pdf_page"] in table_pages,
                        "financial_figures_validated": False,
                        "chunk_version": CHUNK_VERSION,
                    },
                }
            )
            if end >= len(text):
                break
            start = max(start + 1, end - overlap)
            ordinal += 1
    return result


def retrieve(
    store,
    symbol: str,
    question: str,
    *,
    kinds: list[str] | None = None,
    published_before: str | None = None,
) -> list[dict]:
    query = keyword_query(question)
    if not query:
        return []
    candidates = store.rpc(
        "finn_keyword_search",
        {
            "p_symbol": symbol,
            "p_query": query,
            "p_kinds": kinds,
            "p_published_before": published_before,
            "p_limit": 30,
        },
    )
    # Prevent one annual-report page or one document from crowding out every transcript.
    pages, documents = Counter(), Counter()
    selected = []
    for candidate in candidates:
        page_key = (candidate["document_id"], candidate["pdf_page"])
        if pages[page_key] >= 2 or documents[candidate["document_id"]] >= 4:
            continue
        selected.append(candidate)
        pages[page_key] += 1
        documents[candidate["document_id"]] += 1
        if len(selected) == 10:
            break
    if selected:
        ids = ",".join(sorted({item["document_id"] for item in selected}))
        documents = store.rows("finn_documents", id="in.(" + ids + ")", select="id,final_url")
        direct = {document["id"]: document["final_url"] for document in documents}
        for item in selected:
            item["document_url"] = direct.get(item["document_id"], item["source_url"])
    return selected
