"""Company-filtered keyword/semantic search with deterministic Reciprocal Rank Fusion."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import re
import time
import uuid

import httpx

from finn import embeddings
from finn.services import DependencyError, MissingConfiguration

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


@dataclass(frozen=True)
class RetrievalSettings:
    candidates: int = 30
    limit: int = 10
    rrf_k: int = 10
    semantic_weight: float = 2.0
    page_cap: int = 2
    document_cap: int = 4
    adaptive_document_cap: bool = True


SETTINGS = RetrievalSettings()
RETRIEVAL_VERSION = "hybrid-rrf-v1"


def retrieval_profile(store, symbol: str, *, strategy=None, settings=SETTINGS) -> dict:
    if not embeddings.enabled() or strategy == "keyword":
        return {"mode": "keyword", "state": "disabled"}
    try:
        index = embeddings.status(store, symbol)
        ready = index["total"] > 0 and index["ready"] == index["total"]
        return {
            "mode": "hybrid" if ready else "keyword",
            "state": "ready" if ready else "indexing",
            "model": embeddings.model_name(),
            "embedding_version": embeddings.VERSION,
            "index": index,
            "version": RETRIEVAL_VERSION,
            "settings": asdict(settings),
        }
    except (
        DependencyError,
        MissingConfiguration,
        httpx.HTTPError,
        ValueError,
        KeyError,
        TypeError,
    ):
        return {"mode": "keyword", "state": "unavailable"}


def profile_identity(profile: dict) -> dict | None:
    if profile["state"] == "disabled":
        return None  # Keep the original keyword answer cache usable after rollback.
    result = {key: value for key, value in profile.items() if key != "index"}
    if profile["mode"] == "hybrid":
        result["index_fingerprint"] = profile["index"]["fingerprint"]
    # A partial index never changes keyword ranking, so do not burn answer calls
    # for every batch. Completion changes the identity to the full hybrid profile.
    return result


def reciprocal_rank_fusion(
    keyword: list[dict], semantic: list[dict], *, k=60, semantic_weight=1.0
) -> list[dict]:
    scores, records, ranks = Counter(), {}, {}
    for name, candidates, weight in [
        ("keyword", keyword, 1.0),
        ("semantic", semantic, semantic_weight),
    ]:
        seen = set()
        for rank, item in enumerate(candidates, 1):
            key = item["chunk_id"]
            if key in seen:
                continue
            seen.add(key)
            records.setdefault(key, item)
            scores[key] += weight / (k + rank)
            ranks.setdefault(key, {})[name] = rank
    return [
        {**records[key], "rrf_score": scores[key], "retrieval_ranks": ranks[key]}
        for key in sorted(records, key=lambda key: (-scores[key], key))
    ]


def diversify(candidates: list[dict], settings=SETTINGS) -> list[dict]:
    pages, documents = Counter(), Counter()
    count = len({item["document_id"] for item in candidates}) or 1
    document_cap = (
        max(settings.document_cap, (settings.limit + count - 1) // count)
        if settings.adaptive_document_cap
        else settings.document_cap
    )
    selected = []
    for candidate in candidates:
        page_key = (candidate["document_id"], candidate["pdf_page"])
        if (
            pages[page_key] >= settings.page_cap
            or documents[candidate["document_id"]] >= document_cap
        ):
            continue
        selected.append(candidate)
        pages[page_key] += 1
        documents[candidate["document_id"]] += 1
        if len(selected) == settings.limit:
            break
    return selected


def retrieve_with_diagnostics(
    store,
    symbol: str,
    question: str,
    *,
    kinds: list[str] | None = None,
    published_before: str | None = None,
    document_ids: list[str] | None = None,
    published_after: str | None = None,
    reporting_period: str | None = None,
    metadata_filter: dict | None = None,
    strategy=None,
    settings=SETTINGS,
    profile=None,
) -> dict:
    started = time.perf_counter()
    profile = profile or retrieval_profile(store, symbol, strategy=strategy, settings=settings)
    query = keyword_query(question)
    base = {
        "p_symbol": symbol,
        "p_kinds": kinds,
        "p_published_before": published_before,
        "p_limit": settings.candidates,
    }
    extra = {
        "p_document_ids": document_ids,
        "p_published_after": published_after,
        "p_reporting_period": reporting_period,
        "p_metadata": metadata_filter,
    }
    extended = any(value is not None for value in extra.values())
    keyword = (
        store.rpc(
            "finn_keyword_search_v2" if extended else "finn_keyword_search",
            {**base, **(extra if extended else {}), "p_query": query},
        )
        if query
        else []
    )
    semantic, reason, semantic_error = [], None, None
    embedding_calls, query_cached = 0, None
    mode = "keyword"
    if profile["mode"] == "hybrid":
        client = None
        try:
            client = embeddings.EmbeddingClient(store)
            vector = client.embed([" ".join(question.split())], "RETRIEVAL_QUERY")[0]
            semantic = store.rpc(
                "finn_semantic_search",
                {
                    **base,
                    **extra,
                    "p_embedding": vector,
                    "p_model": embeddings.model_name(),
                    "p_version": embeddings.VERSION,
                },
            )
            mode = "hybrid"
        except embeddings.EmbeddingUnavailable as exc:
            reason, semantic_error = "semantic_unavailable", exc.reason
        except (
            DependencyError,
            MissingConfiguration,
            httpx.HTTPError,
            ValueError,
            KeyError,
            TypeError,
        ):
            reason = "semantic_unavailable"
        finally:
            if client:
                embedding_calls = getattr(client, "calls", 0)
                query_cached = bool(getattr(client, "cache_hits", 0))
                client.close()
    elif profile["state"] in ["indexing", "unavailable"]:
        reason = "index_incomplete" if profile["state"] == "indexing" else "semantic_unavailable"
    candidates = (
        reciprocal_rank_fusion(
            keyword, semantic, k=settings.rrf_k, semantic_weight=settings.semantic_weight
        )
        if mode == "hybrid"
        else keyword
    )
    selected = diversify(candidates, settings)
    if selected:
        ids = ",".join(sorted({item["document_id"] for item in selected}))
        documents = store.rows("finn_documents", id="in.(" + ids + ")", select="id,final_url")
        direct = {document["id"]: document["final_url"] for document in documents}
        for item in selected:
            item["document_url"] = direct.get(item["document_id"], item["source_url"])
    return {
        "evidence": selected,
        "mode": mode,
        "fallback_reason": reason,
        "semantic_error": semantic_error,
        "profile": profile,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "keyword_candidates": keyword,
        "semantic_candidates": semantic,
        "embedding_provider_calls": embedding_calls,
        "query_embedding_cached": query_cached,
    }


def retrieve(store, symbol: str, question: str, **kwargs) -> list[dict]:
    """Compatibility interface; callers needing mode/coverage use the diagnostic result."""
    return retrieve_with_diagnostics(store, symbol, question, **kwargs)["evidence"]
