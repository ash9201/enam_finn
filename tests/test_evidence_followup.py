import copy
from contextlib import contextmanager
from uuid import uuid4

import pytest
from finn import api, evidence, jobs, research
from pydantic import ValidationError

PARENT, CHUNK, DOC, OTHER, LATER = [str(uuid4()) for _ in range(5)]
BODY = "Management said the company operates on a cost-plus model."


def passage(key=CHUNK, document=DOC):
    return {
        "id": key,
        "chunk_id": key,
        "document_id": document,
        "pdf_page": 3,
        "body": BODY,
        "metadata": {},
        "kind": "transcript",
        "source_url": "https://issuer.example/call.pdf",
        "document_url": "https://issuer.example/call.pdf",
        "discovery_label": "Jun 2026",
        "published_at": None,
        "reporting_period": None,
        "fetched_at": "2026-10-31T00:00:00Z",
    }


def citation():
    row = passage()
    return {
        "id": CHUNK,
        "document_id": DOC,
        "pdf_page": 3,
        "quote": BODY,
        "source_url": row["source_url"],
        "document_label": "Jun 2026",
        "kind": "transcript",
        "published_at": None,
        "reporting_period": None,
        "fetched_at": row["fetched_at"],
    }


class Store:
    def __init__(self):
        self.saved = []
        self.body = BODY
        self.claims = [
            {"statement": "Management describes a cost-plus model.", "citation": citation()}
        ]
        self.dates = {DOC: "May 25, 2026", OTHER: "April 10, 2026", LATER: "October 16, 2026"}
        self.active = []
        self.inserted = []

    def rows(self, table, **filters):
        if table == "finn_research_cache":
            if "cache_key" in filters:
                return [r for r in self.saved if r["cache_key"] == filters["cache_key"][3:]]
            return (
                [{"id": PARENT, "result": {"symbol": "CCL", "claims": self.claims}}]
                if filters.get("symbol") == "eq.CCL"
                else []
            )
        if table == "finn_documents":
            ids = filters.get("id", "")
            return [
                {
                    "id": key,
                    "symbol": "CCL",
                    "kind": "transcript",
                    "source_url": "https://issuer.example/call.pdf",
                    "final_url": "https://issuer.example/call.pdf",
                    "published_at": None,
                    "discovery_label": "Jun 2026",
                    "reporting_period": None,
                    "fetched_at": "2026-10-31T00:00:00Z",
                }
                for key in self.dates
                if key in ids
            ]
        if table == "finn_research_chunks":
            return [{**passage(), "body": self.body}]
        if table == "finn_document_pages":
            date = self.dates[filters["document_id"][3:]]
            return [
                {
                    "pdf_page": page,
                    "layout_text": "Issuer Limited " + date + " Page " + str(page),
                    "metadata": {},
                }
                for page in [2, 3]
            ]
        if table == "finn_companies":
            return [{"manifest": list(self.dates)}]
        if table == "finn_research_jobs":
            return self.active
        raise AssertionError(table)

    def upsert(self, table, rows, **kw):
        self.saved.extend([{**r, "created_at": "2026-10-31T00:00:00Z"} for r in rows])

    def rpc(self, name, values):
        assert name == "finn_research_security_status"
        return {"rls": {str(i): True for i in range(7)}}

    def insert(self, table, row):
        self.inserted.append(row)


def ref(intent="question"):
    return {"research_id": PARENT, "citation_id": CHUNK, "intent": intent}


def test_reference_rejects_browser_supplied_claim_quote_and_invalid_ids():
    with pytest.raises(ValidationError):
        evidence.EvidenceReference(**ref(), quote="Pretend this is evidence")
    with pytest.raises(ValidationError):
        evidence.EvidenceReference(research_id="invented", citation_id=CHUNK)


def test_anchor_is_company_bound_and_must_belong_to_answer():
    store = Store()
    with pytest.raises(ValueError, match="company"):
        evidence.resolve_context(store, "INFY", ref())
    with pytest.raises(ValueError, match="does not belong"):
        evidence.resolve_context(store, "CCL", {**ref(), "citation_id": str(uuid4())})
    store.body = "The original source text has changed completely."
    with pytest.raises(ValueError, match="changed"):
        evidence.resolve_context(store, "CCL", ref())


def test_primary_header_date_is_separate_from_discovery_label():
    context, anchor = evidence.resolve_context(Store(), "CCL", ref())
    assert context["citation"]["document_label"] == "Jun 2026"
    assert context["citation"]["published_at"] is None
    assert anchor["document_date"] == "2026-05-25"
    assert anchor["document_date_basis"] == "Repeated call header"


def test_multiple_claims_on_one_passage_preserve_the_selected_claim():
    store = Store()
    store.claims.append(
        {"statement": "A different claim on the same passage.", "citation": citation()}
    )
    with pytest.raises(ValueError, match="multiple claims"):
        evidence.resolve_context(store, "CCL", ref())
    context, _ = evidence.resolve_context(store, "CCL", {**ref(), "claim_index": 1})
    assert context["claim"] == store.claims[1]["statement"] and context["claim_index"] == 1
    with pytest.raises(ValueError, match="does not belong"):
        evidence.resolve_context(store, "CCL", {**ref(), "claim_index": 2})


def test_single_date_does_not_establish_call_chronology():
    store = Store()
    store.rows = lambda *a, **kw: [{"pdf_page": 1, "layout_text": "May 25, 2026", "metadata": {}}]
    assert (
        evidence.document_date(store, {"id": DOC, "kind": "transcript", "published_at": None}) == {}
    )


@pytest.mark.parametrize(
    "pages",
    [
        ["May 25, 2026 and May 25 2026"],
        ["May 25, 2026 and July 28, 2026", "May 25, 2026 and July 28, 2026"],
    ],
)
def test_date_recurrence_requires_distinct_pages_and_unambiguous_date(pages):
    store = Store()
    store.rows = lambda *a, **kw: [
        {"pdf_page": i + 1, "layout_text": text, "metadata": {}} for i, text in enumerate(pages)
    ]
    assert not evidence.document_date(
        store, {"id": DOC, "kind": "transcript", "published_at": None}
    )


def test_later_retrieval_targets_other_dated_documents_not_just_anchor(monkeypatch):
    store = Store()
    context, anchor = evidence.resolve_context(store, "CCL", ref("later"))
    calls = []

    def retrieve(s, symbol, question, **kw):
        calls.append(kw)
        return {
            "evidence": [passage(), passage(str(uuid4()), OTHER), passage(str(uuid4()), LATER)],
            "mode": "keyword",
            "fallback_reason": None,
            "latency_ms": 1,
        }

    monkeypatch.setattr(evidence, "retrieve_with_diagnostics", retrieve)
    result = evidence.retrieve_followup(
        store, "CCL", "What happened later?", context, anchor, {"mode": "keyword"}
    )
    assert calls[-1]["document_ids"] == [LATER]
    assert result["other_document_count"] == 1
    assert {r["document_id"] for r in result["evidence"]} == {DOC, LATER}


def setup_research(monkeypatch, store, intent="question", other=True):
    context, anchor = evidence.resolve_context(store, "CCL", ref(intent))
    monkeypatch.setattr(
        evidence, "resolve_context", lambda *a: (copy.deepcopy(context), dict(anchor))
    )
    monkeypatch.setattr(
        research,
        "ensure_corpus",
        lambda *a, **kw: {
            "name": "CCL Products",
            "corpus_fingerprint": "same-corpus",
            "source_checked_at": "2026-10-31T00:00:00Z",
            "coverage": {"transcripts": 2, "annual_reports": 1, "notes": []},
        },
    )
    monkeypatch.setattr(
        research, "retrieval_profile", lambda *a: {"mode": "keyword", "state": "disabled"}
    )
    monkeypatch.setattr(
        evidence,
        "retrieve_followup",
        lambda *a: {
            "evidence": [anchor] + ([passage(LATER, LATER)] if other else []),
            "mode": "keyword",
            "fallback_reason": None,
            "latency_ms": 2,
            "other_document_count": int(other),
            "later_document_ids": [LATER] if other else [],
            "chronology_available": True,
        },
    )
    return context


def test_repetition_uses_calls_and_rejects_duplicate_versions_of_same_call(monkeypatch):
    store = Store()
    store.dates[OTHER] = store.dates[DOC]
    context, anchor = evidence.resolve_context(store, "CCL", ref("repeated"))
    scopes = []

    def retrieve(*args, **kwargs):
        scopes.append(kwargs)
        return {
            "evidence": [passage(), passage(str(uuid4()), OTHER), passage(str(uuid4()), LATER)],
            "mode": "keyword",
            "fallback_reason": None,
            "latency_ms": 1,
        }

    monkeypatch.setattr(evidence, "retrieve_with_diagnostics", retrieve)
    result = evidence.retrieve_followup(store, "CCL", "Was it repeated?", context, anchor, {})
    assert all(scope["kinds"] == ["transcript"] for scope in scopes)
    assert {row["document_id"] for row in result["evidence"]} == {DOC, LATER}
    assert result["other_document_count"] == 1


def test_later_scope_requires_a_verified_anchor_date(monkeypatch):
    store = Store()
    context, anchor = evidence.resolve_context(store, "CCL", ref("later"))
    anchor.pop("document_date")
    monkeypatch.setattr(
        evidence,
        "retrieve_with_diagnostics",
        lambda *a, **kw: {
            "evidence": [passage(str(uuid4()), LATER)],
            "mode": "keyword",
            "fallback_reason": None,
            "latency_ms": 1,
        },
    )
    result = evidence.retrieve_followup(store, "CCL", "What happened later?", context, anchor, {})
    assert not result["chronology_available"] and not result["later_document_ids"]
    assert not result["other_document_count"]


def test_context_cache_is_separate_and_cannot_be_published(monkeypatch):
    store = Store()
    context = setup_research(monkeypatch, store)
    observed = []

    def generate(s, question, passages, model, **kw):
        observed.append(kw["context"]["citation_id"])
        return research.DraftAnswer(
            answerable=True,
            claims=[
                research.DraftClaim(
                    statement="Management describes a cost-plus model.",
                    evidence_id=LATER,
                    quote=BODY,
                )
            ],
        ), {}

    monkeypatch.setattr(research, "generate", generate)
    first = research.research_company(
        store, "CCL", "What does this mean?", context_reference=ref(), publish=True
    )
    repeated = research.research_company(
        store, "CCL", "What does this mean?", context_reference=ref()
    )
    assert first["evidence_context"]["citation_id"] == CHUNK
    assert repeated["cached"] and len(observed) == 1
    assert store.saved[0]["is_public"] is False
    changed = copy.deepcopy(context)
    changed["citation_id"] = str(uuid4())
    monkeypatch.setattr(evidence, "resolve_context", lambda *a: (changed, passage()))
    research.research_company(store, "CCL", "What does this mean?", context_reference=ref())
    assert len(observed) == 2 and len({r["cache_key"] for r in store.saved}) == 2


def test_no_later_evidence_abstains_without_model_call(monkeypatch):
    store = Store()
    setup_research(monkeypatch, store, "later", other=False)
    monkeypatch.setattr(
        research,
        "generate",
        lambda *a, **kw: pytest.fail("Anchor alone must not be assessed as later evidence"),
    )
    result = research.research_company(
        store, "CCL", "Did later evidence support this?", context_reference=ref("later")
    )
    assert result["status"] == "insufficient_evidence" and not result["claims"]
    assert "Not yet assessable" in result["investigation"]["assessment"]


def test_general_evidence_question_can_answer_without_chronology(monkeypatch):
    store = Store()
    context = setup_research(monkeypatch, store, other=False)
    context["citation"].pop("document_date")
    monkeypatch.setattr(
        evidence,
        "retrieve_followup",
        lambda *a: {
            "evidence": [passage()],
            "mode": "keyword",
            "fallback_reason": None,
            "latency_ms": 1,
            "other_document_count": 0,
            "later_document_ids": [],
            "chronology_available": False,
        },
    )
    monkeypatch.setattr(
        research,
        "generate",
        lambda *a, **kw: (
            research.DraftAnswer(
                answerable=True,
                claims=[
                    research.DraftClaim(
                        statement="Management describes a cost-plus model.",
                        evidence_id=CHUNK,
                        quote=BODY,
                    )
                ],
            ),
            {},
        ),
    )
    result = research.research_company(
        store, "CCL", "What did management describe?", context_reference=ref()
    )
    assert result["status"] == "answered" and result["claims"]
    assert not result["evidence_context"]["citation"].get("document_date")


def test_followup_withholds_a_quote_cut_off_before_the_supporting_fact():
    source = passage()
    source["body"] = "The trend was accentuated when coffee prices"
    draft = research.DraftAnswer(
        answerable=True,
        claims=[
            research.DraftClaim(
                statement="Management said the trend was accentuated when coffee prices fell.",
                evidence_id=CHUNK,
                quote=source["body"],
            )
        ],
    )
    claims, withheld = research.validate_answer(draft, [source], require_complete_quotes=True)
    assert not claims and withheld == 1


def test_job_deduplication_distinguishes_general_and_contextual_requests(monkeypatch):
    store = Store()
    store.active = [
        {
            "id": "general",
            "symbol": "CCL",
            "question": "What does this mean?",
            "refresh": False,
            "result": {},
        }
    ]

    @contextmanager
    def open_store():
        yield store

    monkeypatch.setattr(api, "open_store", open_store)
    monkeypatch.setattr(jobs, "expire_stale_jobs", lambda s: None)
    submitted = []
    monkeypatch.setattr(jobs, "submit", submitted.append)
    assert (
        api.start_research(api.ResearchRequest(symbol="CCL", question="What does this mean?"))[
            "job_id"
        ]
        == "general"
    )
    started = api.start_research(
        api.ResearchRequest(symbol="CCL", question="What does this mean?", context=ref())
    )
    assert started["job_id"] != "general" and len(submitted) == 1
    assert store.inserted[0]["result"]["_request"]["context"] == ref()


def test_worker_keeps_context_and_history_from_persisted_request(monkeypatch):
    store = Store()
    store.active = [
        {
            "id": PARENT,
            "state": "queued",
            "symbol": "CCL",
            "question": "Was this repeated?",
            "refresh": False,
            "result": {"_request": {"context": ref("repeated"), "include_history": True}},
        }
    ]
    patches, seen = [], []
    store.patch = lambda table, values, **kw: patches.append(values)

    @contextmanager
    def open_store():
        yield store

    monkeypatch.setattr(jobs, "open_store", open_store)
    monkeypatch.setattr(
        jobs, "research_company", lambda *args, **kw: seen.append(kw) or {"status": "answered"}
    )
    jobs.run_job(PARENT)
    assert seen[0]["context_reference"] == ref("repeated")
    assert seen[0]["include_history"] is True
    assert patches[-1]["state"] == "completed"


def test_later_answers_cannot_relabel_anchor_claims_as_new_evidence(monkeypatch):
    store = Store()
    setup_research(monkeypatch, store, "later")
    monkeypatch.setattr(
        research,
        "generate",
        lambda *a, **kw: (
            research.DraftAnswer(
                answerable=True,
                claims=[
                    research.DraftClaim(
                        statement="Management describes a cost-plus model.",
                        evidence_id=CHUNK,
                        quote=BODY,
                    )
                ],
            ),
            {},
        ),
    )
    result = research.research_company(
        store, "CCL", "Did later evidence support this?", context_reference=ref("later")
    )
    assert result["status"] == "insufficient_evidence" and result["claims"] == []
