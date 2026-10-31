import hashlib
import json

import httpx
import pytest

from finn import embeddings, retrieval


@pytest.fixture(autouse=True)
def feature_off(monkeypatch):
    monkeypatch.setenv("FINN_ENABLE_SEMANTIC_SEARCH", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-a-real-credential")
    monkeypatch.setattr(embeddings, "_cooldowns", {})


def candidate(key, page=1, document="doc"):
    return {
        "chunk_id": key,
        "document_id": document,
        "pdf_page": page,
        "body": "The company manufactures coffee for international customers.",
        "source_url": "https://issuer.example/report.pdf",
        "metadata": {"financial_figures_validated": False},
    }


class Store:
    def __init__(self):
        self.cache = []
        self.calls = []
        self.saved = []
        self.reservation = {"allowed": True}
        self.index = {"total": 5, "ready": 5, "secure": True, "fingerprint": "index-v1"}
        self.keyword = [candidate("keyword", page=1), candidate("both", page=2)]
        self.semantic = [candidate("semantic", page=3), candidate("both", page=2)]

    def rows(self, table, **filters):
        if table == "finn_embedding_cache":
            return [
                row
                for row in self.cache
                if all(
                    str(row[key]) == filters[key][3:]
                    for key in ["model", "dimensions", "task_type", "version"]
                )
                and row["input_hash"] in filters["input_hash"]
            ]
        return [{"id": "doc", "final_url": "https://issuer.example/direct.pdf"}]

    def upsert(self, table, rows, **kwargs):
        self.saved.extend(rows)
        if table == "finn_embedding_cache":
            self.cache.extend(rows)

    def rpc(self, name, values):
        self.calls.append((name, values))
        if name == "finn_reserve_embedding_request":
            return self.reservation
        if name == "finn_embedding_status":
            return self.index
        if name in ["finn_keyword_search", "finn_keyword_search_v2"]:
            return self.keyword
        if name == "finn_semantic_search":
            return self.semantic
        raise AssertionError(name)


def client(store, handler):
    result = embeddings.EmbeddingClient(store)
    result.client.close()
    result.client = httpx.Client(transport=httpx.MockTransport(handler))
    return result


@pytest.mark.parametrize(
    "value", [[0] * 768, [1] * 767, [float("nan")] * 768, [True] * 768, [float("inf")] * 768]
)
def test_invalid_vectors_are_never_accepted(value):
    with pytest.raises(embeddings.EmbeddingUnavailable):
        embeddings.normalise(value)


def test_normalisation_and_cache_are_task_scoped_and_deduplicated():
    store = Store()
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append((request.url.path, body))
        if request.url.path.endswith("countTokens"):
            return httpx.Response(200, json={"totalTokens": 12})
        return httpx.Response(
            200, json={"embeddings": [{"values": [2.0] + [0.0] * 767} for _ in body["requests"]]}
        )

    model = client(store, handler)
    try:
        first = model.embed(["Source coffee text", "Source coffee text"], "RETRIEVAL_DOCUMENT")
        second = model.embed(["Source coffee text"], "RETRIEVAL_DOCUMENT")
        assert first[0] == first[1] == second[0] == [1.0] + [0.0] * 767
        assert len(calls) == 2  # One token count plus one deduplicated embedding request.
        assert calls[1][1]["requests"][0]["taskType"] == "RETRIEVAL_DOCUMENT"
        assert calls[1][1]["requests"][0]["outputDimensionality"] == 768
        model.embed(["Source coffee text"], "RETRIEVAL_QUERY")
        assert len(calls) == 3  # Token counts can be reused across embedding tasks.
        assert store.cache[0]["input_hash"] == hashlib.sha256(b"Source coffee text").hexdigest()
    finally:
        model.close()


def test_partial_provider_batch_does_not_write_any_cache_vectors():
    store = Store()
    model = client(
        store,
        lambda request: httpx.Response(
            200,
            json={"totalTokens": 20}
            if request.url.path.endswith("countTokens")
            else {"embeddings": [{"values": [1.0] + [0.0] * 767}]},
        ),
    )
    try:
        with pytest.raises(embeddings.EmbeddingUnavailable, match="incomplete_vector_batch"):
            model.embed(["first", "second"], "RETRIEVAL_DOCUMENT")
        assert not store.saved
    finally:
        model.close()


def test_budget_denial_does_not_contact_provider():
    store = Store()
    store.reservation = {"allowed": False, "reason": "daily_budget", "retry_after": 86400}
    model = client(store, lambda request: pytest.fail("Provider called after budget denial"))
    try:
        with pytest.raises(embeddings.EmbeddingUnavailable, match="daily_budget"):
            model.embed(["source"], "RETRIEVAL_DOCUMENT")
    finally:
        model.close()


def test_oversized_input_is_not_silently_truncated():
    store = Store()

    def handler(request):
        assert request.url.path.endswith("countTokens")
        return httpx.Response(200, json={"totalTokens": 2049})

    model = client(store, handler)
    try:
        with pytest.raises(embeddings.EmbeddingUnavailable, match="input_exceeds_model_limit"):
            model.embed(["a" * 2100], "RETRIEVAL_QUERY")
        assert not store.saved
    finally:
        model.close()


def test_feature_off_makes_no_semantic_or_embedding_calls():
    store = Store()
    result = retrieval.retrieve_with_diagnostics(store, "CCL", "coffee products")
    assert result["mode"] == "keyword" and result["fallback_reason"] is None
    assert [name for name, _ in store.calls] == ["finn_keyword_search"]


def test_partial_index_falls_back_without_query_embedding(monkeypatch):
    monkeypatch.setenv("FINN_ENABLE_SEMANTIC_SEARCH", "true")
    store = Store()
    store.index["ready"] = 1
    monkeypatch.setattr(
        embeddings,
        "EmbeddingClient",
        lambda *a, **kw: pytest.fail("Partial index sent to semantic retrieval"),
    )
    result = retrieval.retrieve_with_diagnostics(store, "CCL", "coffee products")
    assert result["mode"] == "keyword" and result["fallback_reason"] == "index_incomplete"
    assert retrieval.profile_identity(result["profile"]).get("index_fingerprint") is None


def test_rrf_promotes_agreement_without_mixing_raw_scores():
    keyword = [{**candidate("a"), "rank": 1000}, candidate("b"), candidate("a")]
    semantic = [{**candidate("c"), "rank": 0.99}, candidate("b")]
    fused = retrieval.reciprocal_rank_fusion(keyword, semantic)
    assert fused[0]["chunk_id"] == "b"
    assert fused[0]["rrf_score"] == pytest.approx(2 / 62)
    assert len(fused) == 3


def test_hybrid_filters_are_identical_and_citations_keep_original_metadata(monkeypatch):
    monkeypatch.setenv("FINN_ENABLE_SEMANTIC_SEARCH", "true")

    class QueryClient:
        def __init__(self, *a, **kw):
            pass

        def embed(self, texts, task):
            assert task == "RETRIEVAL_QUERY"
            return [[1.0] + [0.0] * 767]

        def close(self):
            pass

    monkeypatch.setattr(embeddings, "EmbeddingClient", QueryClient)
    store = Store()
    result = retrieval.retrieve_with_diagnostics(
        store,
        "UNPREPARED",
        "coffee business",
        kinds=["annual_report"],
        document_ids=["doc"],
        published_before="2026-01-01T00:00:00Z",
        published_after="2025-01-01T00:00:00Z",
        reporting_period="FY2025",
        metadata_filter={"financial_figures_validated": False},
    )
    calls = dict(store.calls)
    left, right = calls["finn_keyword_search_v2"], calls["finn_semantic_search"]
    for field in [
        "p_symbol",
        "p_kinds",
        "p_document_ids",
        "p_published_before",
        "p_published_after",
        "p_reporting_period",
        "p_metadata",
    ]:
        assert left[field] == right[field]
    assert result["mode"] == "hybrid" and result["evidence"][0]["chunk_id"] == "both"
    assert result["evidence"][0]["metadata"]["financial_figures_validated"] is False
    assert result["evidence"][0]["document_url"] == "https://issuer.example/direct.pdf"


def test_embedding_failure_preserves_keyword_answer_path(monkeypatch):
    monkeypatch.setenv("FINN_ENABLE_SEMANTIC_SEARCH", "true")

    def unavailable(*a, **kw):
        raise embeddings.EmbeddingUnavailable("provider_throttled", 60)

    monkeypatch.setattr(embeddings, "EmbeddingClient", unavailable)
    store = Store()
    result = retrieval.retrieve_with_diagnostics(store, "CCL", "coffee business")
    assert result["mode"] == "keyword" and result["fallback_reason"] == "semantic_unavailable"
    assert [r["chunk_id"] for r in result["evidence"]] == ["keyword", "both"]


def test_ready_index_identity_changes_with_model_or_content(monkeypatch):
    monkeypatch.setenv("FINN_ENABLE_SEMANTIC_SEARCH", "true")
    store = Store()
    first = retrieval.profile_identity(retrieval.retrieval_profile(store, "CCL"))
    store.index["fingerprint"] = "rechunked"
    second = retrieval.profile_identity(retrieval.retrieval_profile(store, "CCL"))
    assert first != second
    monkeypatch.setenv("GEMINI_EMBEDDING_MODEL", "another-model")
    assert second != retrieval.profile_identity(retrieval.retrieval_profile(store, "CCL"))


def test_backfill_resumes_stored_vectors_after_database_disconnect(monkeypatch):
    class BackfillStore(Store):
        def __init__(self):
            super().__init__()
            self.items = [
                {"chunk_id": str(i), "body": text, "body_hash": embeddings.text_hash(text)}
                for i, text in enumerate(["first source", "second source", "third source"])
            ]
            self.completed = set()
            self.disconnect = True

        def rpc(self, name, values):
            if name == "finn_embedding_status":
                return {**self.index, "ready": len(self.completed), "total": len(self.items)}
            if name == "finn_pending_embeddings":
                return [dict(r) for r in self.items if r["chunk_id"] not in self.completed]
            if name == "finn_store_chunk_embedding":
                if len(self.completed) == 1 and self.disconnect:
                    self.disconnect = False
                    raise httpx.RemoteProtocolError("Simulated connection drop")
                self.completed.add(values["p_chunk_id"])
                return True
            return super().rpc(name, values)

    store = BackfillStore()
    providers = []
    real_client = embeddings.EmbeddingClient

    def factory(store, **kwargs):
        model = real_client(store, **kwargs)
        model.client.close()

        def handler(request):
            providers.append(request.url.path)
            payload = json.loads(request.content)
            return httpx.Response(
                200,
                json={"totalTokens": 12}
                if request.url.path.endswith("countTokens")
                else {"embeddings": [{"values": [1.0] + [0.0] * 767} for _ in payload["requests"]]},
            )

        model.client = httpx.Client(transport=httpx.MockTransport(handler))
        return model

    monkeypatch.setattr(embeddings, "EmbeddingClient", factory)
    interrupted = embeddings.backfill(store, "ARBITRARY", max_batches=1, wait=False)
    assert interrupted["state"] == "pending" and interrupted["ready"] == 1
    assert interrupted["reason"] == "storage_unavailable"
    resumed = embeddings.backfill(store, "ARBITRARY", max_batches=2, wait=False)
    assert resumed["state"] == "completed" and resumed["ready"] == 3
    assert resumed["provider_calls"] == 0 and resumed["cache_hits"] == 2
    assert len(providers) == 2  # One count and embedding batch; no paid duplicate work.


def test_semantic_transport_error_falls_back(monkeypatch):
    monkeypatch.setenv("FINN_ENABLE_SEMANTIC_SEARCH", "true")

    def disconnected(*a, **kw):
        raise httpx.RemoteProtocolError("Simulated embedding cache connection drop")

    monkeypatch.setattr(embeddings, "EmbeddingClient", disconnected)
    result = retrieval.retrieve_with_diagnostics(Store(), "CCL", "coffee business")
    assert result["mode"] == "keyword" and result["fallback_reason"] == "semantic_unavailable"


def test_runtime_fallback_answer_is_not_saved_under_hybrid_cache_key(monkeypatch):
    from finn import research

    monkeypatch.setenv("FINN_ENABLE_SEMANTIC_SEARCH", "true")
    store = Store()
    original_rows = store.rows
    store.rows = lambda table, **kw: (
        [] if table == "finn_research_cache" else original_rows(table, **kw)
    )
    for row in store.keyword:
        row.update(
            kind="transcript",
            discovery_label="Primary call",
            published_at=None,
            reporting_period=None,
            fetched_at="2026-10-31T00:00:00Z",
        )
    monkeypatch.setattr(
        research,
        "ensure_corpus",
        lambda *a, **kw: {
            "name": "Coffee Manufacturer",
            "corpus_fingerprint": "corpus-v1",
            "source_checked_at": "2026-10-31T00:00:00Z",
            "coverage": {"notes": [], "transcripts": 2},
        },
    )
    monkeypatch.setattr(
        research,
        "generate",
        lambda s, q, evidence, model: (
            research.DraftAnswer(
                answerable=True,
                claims=[
                    research.DraftClaim(
                        statement="The company manufactures coffee for international customers.",
                        evidence_id=evidence[0]["chunk_id"],
                        quote=evidence[0]["body"],
                    )
                ],
            ),
            {},
        ),
    )

    def unavailable(*a, **kw):
        raise embeddings.EmbeddingUnavailable("provider_throttled", 60)

    monkeypatch.setattr(embeddings, "EmbeddingClient", unavailable)
    result = research.research_company(store, "ANYTICKER", "What does the business make?")
    assert result["status"] == "answered" and result["retrieval_mode"] == "keyword"
    assert result["claims"][0]["citation"]["pdf_page"] == 1
    assert not store.saved


@pytest.mark.parametrize("fail_second_document", [False, True])
def test_generic_ingestion_only_schedules_embeddings_after_manifest_activation(
    monkeypatch, fail_second_document
):
    from contextlib import nullcontext
    from finn import corpus

    events, current = [], {}

    class NewCompanyStore:
        def rows(self, *a, **kw):
            return []

        def upsert(self, *a, **kw):
            pass

        def patch(self, table, values, **filters):
            current.update(values)
            events.append("manifest")

    monkeypatch.setattr(corpus, "public_client", lambda: nullcontext(object()))
    monkeypatch.setattr(
        corpus,
        "resolve_company",
        lambda client, symbol: {"symbol": symbol, "name": "Unprepared Issuer", "isin": "TEST"},
    )
    monkeypatch.setattr(
        corpus,
        "discover_documents",
        lambda client, company: {
            "documents": {
                "annual_report": [{"kind": "annual_report", "id": "report"}],
                "transcript": [
                    {"kind": "transcript", "id": "call-a"},
                    {"kind": "transcript", "id": "call-b"},
                ],
            }
        },
    )

    def ingest(store, client, company, document, **kwargs):
        assert company["symbol"] == "UNPREPARED"
        if fail_second_document and document["id"] == "call-a":
            raise ValueError("Original transcript unavailable")
        return {"id": document["id"], "sha256": document["id"], "kind": document["kind"]}

    def schedule(symbol):
        assert symbol == "UNPREPARED" and len(current["manifest"]) == 3
        events.append("embedding")

    monkeypatch.setattr(corpus, "ingest_document", ingest)
    monkeypatch.setattr(embeddings, "schedule_backfill", schedule)
    if fail_second_document:
        with pytest.raises(ValueError, match="unavailable"):
            corpus.ensure_corpus(NewCompanyStore(), "UNPREPARED")
        assert not events and "manifest" not in current
    else:
        result = corpus.ensure_corpus(NewCompanyStore(), "UNPREPARED")
        assert result["coverage"]["annual_reports"] == 1
        assert events == ["manifest", "embedding"]


@pytest.mark.parametrize("response", [[], {"embeddings": [None]}])
def test_malformed_embedding_response_remains_recoverable(response):
    store = Store()
    model = client(
        store,
        lambda request: httpx.Response(
            200, json={"totalTokens": 4} if request.url.path.endswith("countTokens") else response
        ),
    )
    try:
        with pytest.raises(embeddings.EmbeddingUnavailable):
            model.embed(["source"], "RETRIEVAL_DOCUMENT")
        assert not store.saved
    finally:
        model.close()


def test_provider_daily_quota_uses_retry_metadata_and_does_not_retry_network():
    store = Store()
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("countTokens"):
            return httpx.Response(200, json={"totalTokens": 4})
        return httpx.Response(
            429,
            json={
                "error": {
                    "details": [
                        {
                            "violations": [
                                {
                                    "quotaId": "EmbedContentRequestsPerDayPerUserPerProjectPerModel-FreeTier"
                                }
                            ]
                        },
                        {"retryDelay": "3600s"},
                    ]
                }
            },
        )

    model = client(store, handler)
    try:
        with pytest.raises(embeddings.EmbeddingUnavailable) as error:
            model.embed(["source"], "RETRIEVAL_DOCUMENT")
        assert error.value.reason == "provider_daily_budget"
        assert error.value.retry_after == 3600
        assert all(
            values["p_rpd"] == 800
            for name, values in store.calls
            if name == "finn_reserve_embedding_request"
        )
        with pytest.raises(embeddings.EmbeddingUnavailable, match="provider_daily_budget"):
            model.embed(["different question"], "RETRIEVAL_QUERY")
        assert len(requests) == 2 and not store.saved
    finally:
        model.close()


def test_document_diversity_cap_fills_single_document_budget_without_losing_page_cap():
    rows = [candidate(str(i), page=i // 2 + 1) for i in range(20)]
    selected = retrieval.diversify(rows)
    assert len(selected) == 10 and len({r["pdf_page"] for r in selected}) == 5
    legacy = retrieval.diversify(rows, retrieval.RetrievalSettings(adaptive_document_cap=False))
    assert len(legacy) == 4
    three_docs = [candidate(str(i), page=i, document="doc-" + str(i // 8)) for i in range(24)]
    selected = retrieval.diversify(three_docs)
    assert len(selected) == 10
    assert (
        max(
            sum(r["document_id"] == doc for r in selected)
            for doc in {r["document_id"] for r in selected}
        )
        <= 4
    )


def test_quote_about_margin_cannot_validate_an_added_ebitda_claim():
    from finn.research import DraftAnswer, DraftClaim, validate_answer, supported_metrics

    row = {
        **candidate("margin"),
        "body": "Our margin profile does not change when green coffee prices decrease.",
        "kind": "transcript",
    }
    draft = DraftAnswer(
        answerable=True,
        claims=[
            DraftClaim(
                statement="Margins and EBITDA do not change when green coffee prices decrease.",
                quote=row["body"],
                evidence_id="margin",
            )
        ],
    )
    claims, withheld = validate_answer(draft, [row])
    assert not claims and withheld == 1
    assert supported_metrics("EBITDA per kilogram is stable.", "Our EBITDA per kilogram is stable.")
    assert not supported_metrics("EBIT is stable.", "EBITDA is stable.")
