"""Behavioral checks for useful, fast research and verified image recovery."""

import hashlib
import uuid
from contextlib import contextmanager
from copy import deepcopy

from finn import api, corpus, jobs, research, retrieval
from finn.documents import resolve_source_quote
from finn.financial_vision import verified_table


def source(key, text, *, kind="transcript"):
    return {
        "chunk_id": key,
        "document_id": str(uuid.uuid4()),
        "body": text,
        "pdf_page": 3,
        "kind": kind,
        "metadata": {},
        "source_url": "https://issuer.example/call.pdf",
        "discovery_label": "Jul 2026",
        "published_at": None,
        "reporting_period": None,
        "fetched_at": "2026-10-31T00:00:00Z",
    }


def test_synthesis_keeps_each_supporting_source_and_missing_support_withholds():
    evidence = [
        source("a", "We supply instant coffee to private label customers."),
        source("b", "Our branded coffee is distributed through retail and online channels."),
    ]
    draft = research.DraftAnswer(
        answerable=True,
        claims=[
            research.DraftClaim(
                statement="The business combines private label supply with branded retail and online distribution.",
                evidence_id="a",
                quote=evidence[0]["body"],
                supporting_evidence=[{"evidence_id": "b", "quote": evidence[1]["body"]}],
            )
        ],
    )
    claims, withheld = research.validate_answer(draft, evidence)
    assert withheld == 0 and len(claims[0]["citations"]) == 2
    assert not research.validate_answer(draft, evidence[:1])[0]


def test_annual_prose_counts_are_usable_but_financial_amounts_remain_gated():
    src = source("a", "We serve customers in 50 countries through 3 plants.", kind="annual_report")
    draft = research.DraftAnswer(
        answerable=True,
        claims=[research.DraftClaim(statement=src["body"], evidence_id="a", quote=src["body"])],
    )
    assert research.validate_answer(draft, [src])[0]
    src["body"] = "Revenue was INR 100 crore for the quarter."
    draft.claims[0].statement = draft.claims[0].quote = src["body"]
    assert not research.validate_answer(draft, [src])[0]


def test_quote_alignment_accepts_prose_commas_but_not_changed_figures_or_negation():
    raw = "We expect volumes to grow by 15%, which supports the outlook."
    assert resolve_source_quote(raw.replace("%,", "%"), raw) == raw
    assert resolve_source_quote("Revenue was 10000 crore.", "Revenue was 10,000 crore.") is None
    assert resolve_source_quote("We expect growth.", "We do not expect growth.") is None
    original = "Management described the annual production target. It has not yet been achieved. The next update will report progress against that target."
    assert (
        resolve_source_quote(
            "Management described the annual production target. ... The next update will report progress against that target.",
            original,
        )
        == original
    )


def test_contextual_identifiers_do_not_approve_unquoted_financial_values():
    src = {"source_identifiers": ["Q1", "FY27"], "document_date": "2026-07-29"}
    assert research.numbers_with_context(
        "In Q1, management discussed FY27 on July 29, 2026.",
        "Management discussed the outlook.",
        [src],
    )
    assert not research.numbers_with_context(
        "Q1 revenue was INR 1 crore.", "Management discussed the outlook.", [src]
    )


def test_ready_corpus_older_than_a_day_is_reused_without_fabricating_freshness(monkeypatch):
    old = "2026-10-01T00:00:00+00:00"

    class Store:
        def rows(self, table, **kw):
            return (
                [{"symbol": "TEST", "manifest": ["doc"], "source_checked_at": old, "coverage": {}}]
                if table == "finn_companies"
                else [
                    {
                        "id": "doc",
                        "state": "ready",
                        "extraction_notes": {"chunk_version": retrieval.CHUNK_VERSION},
                    }
                ]
            )

    monkeypatch.setattr(
        corpus,
        "public_client",
        lambda: (_ for _ in ()).throw(AssertionError("Unnecessary source acquisition")),
    )
    result = corpus.ensure_corpus(Store(), "TEST")
    assert result["source_checked_at"] == old and result["reused_corpus"]


def test_cached_api_answer_bypasses_a_busy_acquisition_queue(monkeypatch):
    class Store:
        inserted = []

        def rpc(self, name, values):
            return {"rls": {str(i): True for i in range(7)}}

        def insert(self, table, row):
            self.inserted.append(row)

        def rows(self, *args, **kw):
            raise AssertionError("A cached answer should not enter the active-job queue.")

    store = Store()

    @contextmanager
    def connection():
        yield store

    monkeypatch.setattr(api, "open_store", connection)
    monkeypatch.setattr(
        research, "fast_cached_research", lambda *args: {"id": "answer", "cached": True}
    )
    response = api.start_research(
        api.ResearchRequest(symbol="CCL", question="What does the company sell?")
    )
    assert response["state"] == "completed" and response["result"]["cached"]
    assert store.inserted[0]["state"] == "completed"


def test_prepared_research_has_a_separate_worker_lane(monkeypatch):
    calls = []
    monkeypatch.setattr(jobs.executor, "submit", lambda *args: calls.append("acquisition"))
    monkeypatch.setattr(jobs.answer_executor, "submit", lambda *args: calls.append("prepared"))
    jobs.submit("a")
    jobs.submit("b", prepared=True)
    assert calls == ["acquisition", "prepared"]


def reading():
    return {
        "is_income_statement": True,
        "company_name": "Test Limited",
        "basis": "consolidated",
        "currency": "INR",
        "unit": "crore",
        "header": "INR crore, consolidated quarterly results",
        "rows": [
            {
                "metric": "Revenue",
                "definition": "revenue_from_operations",
                "label": "Revenue from operations",
                "cells": [
                    {
                        "period_end": period,
                        "period_kind": kind,
                        "header": period,
                        "raw_value": value,
                    }
                    for period, kind, value in [
                        ("2026-09-30", "quarter", "123.40"),
                        ("2026-06-30", "quarter", "110.00"),
                        ("2025-09-30", "quarter", "100.00"),
                        ("2026-09-30", "half_year", "233.40"),
                    ]
                ],
            }
        ],
    }


def test_two_image_reads_withhold_only_the_disagreeing_cell_and_exclude_ytd():
    first, second = reading(), reading()
    second["rows"][0]["cells"][0]["raw_value"] = "123.45"
    table = verified_table(first, second, 3)
    assert len(table["columns"]) == 2
    assert table["rows"][0]["cells"][1:] == ["110.00", "100.00"]
    assert all(c["period_end"] != "2026-09-30" for c in table["columns"])
    second["currency"] = "USD"
    assert verified_table(first, second, 3) is None


def test_standalone_pat_alias_does_not_change_raw_provider_readings():
    first, second = reading(), reading()
    for frame in [first, second]:
        frame["basis"] = "standalone"
        frame["rows"][0].update(
            metric="PAT", definition="owners_pat", label="Net profit for the period"
        )
    before = deepcopy(first)
    assert verified_table(first, second, 3)["rows"][0]["verified_definition"] == "group_pat"
    assert first == before
    first["basis"] = second["basis"] = "consolidated"
    assert verified_table(first, second, 3) is None


def test_bank_before_minority_label_does_not_hide_group_pat():
    from finn.financials import eligible_rows

    table = {
        "rows": [
            {
                "index": 0,
                "cells": ["Profit before tax and minority interest"],
                "verified_metric": "PBT",
                "text": "Profit before tax and minority interest",
            },
            {
                "index": 1,
                "cells": ["Net profit for the period before minority interest"],
                "verified_metric": "PAT",
                "text": "Net profit for the period before minority interest",
            },
        ]
    }
    assert eligible_rows(table, "PAT")[0]["index"] == 1


def test_page_evidence_resolves_to_immutable_primary_page(monkeypatch):
    from finn import evidence

    doc_id = str(uuid.uuid4())
    text = "Management expects the new manufacturing capacity to be commissioned next quarter."
    digest = hashlib.sha256(text.encode()).hexdigest()
    citation_id = str(uuid.uuid5(uuid.UUID(doc_id), f"page-evidence:3:{digest}"))
    citation = {
        "id": citation_id,
        "document_id": doc_id,
        "pdf_page": 3,
        "quote": text,
        "evidence_scope": "page",
        "page_hash": digest,
    }
    parent = str(uuid.uuid4())

    class Store:
        def rows(self, table, **kw):
            if table == "finn_research_cache":
                return [
                    {
                        "result": {
                            "symbol": "TEST",
                            "claims": [
                                {
                                    "statement": "Management expects an expansion.",
                                    "citation": citation,
                                }
                            ],
                        }
                    }
                ]
            if table == "finn_documents":
                return [
                    {
                        "id": doc_id,
                        "kind": "transcript",
                        "final_url": "https://issuer.example/call.pdf",
                        "source_url": "https://issuer.example/call.pdf",
                        "discovery_label": "Jul 2026",
                    }
                ]
            if table == "finn_research_chunks":
                return []
            if table == "finn_document_pages":
                return [{"layout_text": text, "metadata": {}}]

    monkeypatch.setattr(evidence, "document_date", lambda *args, **kw: {})
    context, anchor = evidence.resolve_context(
        Store(), "TEST", {"research_id": parent, "citation_id": citation_id, "claim_index": 0}
    )
    assert context["citation"]["quote"] == text and anchor["evidence_scope"] == "page"


def test_reported_ebitda_requires_matching_native_and_image_metadata(monkeypatch):
    from finn import reported_metrics as reported

    text = "Example Limited reports quarter ended September 30, 2026. Consolidated EBITDA at Rs 1,000 million."
    fact = {
        "metric": "EBITDA",
        "raw_value": "1000",
        "period_end": "2026-09-30",
        "period_kind": "quarter",
        "basis": "consolidated",
        "currency": "INR",
        "unit": "million",
        "whole_company": True,
        "adjusted": False,
    }
    monkeypatch.setattr(reported, "native_page_texts", lambda *args: [text])
    monkeypatch.setattr(reported, "render_page", lambda *args: b"original-page-image")
    monkeypatch.setattr(reported, "read_reported_facts", lambda *args: {"facts": [fact]})

    class Store:
        def upsert(self, *args):
            assert args[1][0]["metadata"]["contains_table_candidates"] is True
            assert "financial_figures_validated" not in args[1][0]["metadata"]

    doc = {"id": str(uuid.uuid4()), "extraction_notes": {}, "sha256": "original-pdf-digest"}
    tables, _ = reported.extract_reported_ebitda(Store(), doc, b"pdf", "Example Limited")
    assert tables[0]["rows"][0]["cells"] == ["EBITDA", "1,000"]
    assert tables[0]["image_verification"]["method"] == "native_prose_verified_image"
    fact["period_kind"] = "half_year"
    assert not reported.extract_reported_ebitda(Store(), doc, b"pdf", "Example Limited")[0]
    fact["period_kind"] = "quarter"
    fact["raw_value"] = "1001"
    assert not reported.extract_reported_ebitda(Store(), doc, b"pdf", "Example Limited")[0]


def test_interrupted_upsert_retries_identical_data_but_quota_rpc_does_not():
    import httpx
    import pytest
    from finn.store import Store

    requests = []

    def handler(request):
        requests.append(request)
        if len(requests) == 1 or "/rpc/" in request.url.path:
            raise httpx.RemoteProtocolError("response lost")
        return httpx.Response(201)

    store = Store.__new__(Store)
    store.client = httpx.Client(
        base_url="https://db.example", transport=httpx.MockTransport(handler)
    )
    store.upsert("finn_research_cache", [{"id": "stable-id", "result": {"verified": True}}])
    assert len(requests) == 2 and requests[0].content == requests[1].content
    with pytest.raises(httpx.RemoteProtocolError):
        store.rpc("finn_reserve_model_call", {"p_model": "test"})
    assert len(requests) == 3
    store.close()


def test_comparison_financial_context_uses_original_financial_parent():
    from finn.comparison import financial_context

    figure = {"period_end": "2026-09-30", "claim_index": 0}
    claim = {"statement": "Reported EBITDA", "citation": {"id": "financial-citation"}}

    class Store:
        def rows(self, *args, **kwargs):
            return [
                {
                    "result": {
                        "id": "financial-parent",
                        "symbol": "TEST",
                        "company_name": "Example",
                        "source_checked_at": "2026-10-31",
                        "claims": [claim],
                        "financial_results": {
                            "bases": {
                                "consolidated": {
                                    "rows": [{"metric": "EBITDA", "figures": {"latest": figure}}]
                                }
                            }
                        },
                    }
                }
            ]

    result = {
        "id": "comparison-parent",
        "symbol": "TEST",
        "comparison": {
            "metric": "EBITDA",
            "earlier": {"citation": {"quote": "EBITDA outlook", "document_date": "2026-07-01"}},
            "later": {"citation": {"quote": "EBITDA observation"}},
        },
    }
    context = financial_context(Store(), result)["financial_context"]
    assert context["research_id"] == "financial-parent" and context["claim"] == claim
