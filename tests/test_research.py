from copy import deepcopy
from datetime import datetime, timezone
import uuid

import pytest

from finn.api import ResearchRequest
from finn.documents import citation_is_supported, resolve_source_quote
from finn.research import DraftAnswer, validate_answer, supported_numbers
from finn.retrieval import chunk_pages, keyword_query, retrieve


def evidence(kind="transcript"):
    return {
        "chunk_id": "known",
        "document_id": str(uuid.uuid4()),
        "pdf_page": 7,
        "body": "We manufacture cables and electrical products. Management reported revenue of INR 100 crore for the quarter.",
        "metadata": {},
        "source_url": "https://issuer.example/call.pdf",
        "kind": kind,
        "discovery_label": "Oct 2026",
        "published_at": None,
        "reporting_period": None,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def draft(statement, quote, evidence_id="known"):
    return DraftAnswer(
        answerable=True,
        claims=[{"statement": statement, "quote": quote, "evidence_id": evidence_id}],
    )


def test_valid_claim_has_server_resolved_source():
    source = evidence()
    claims, withheld = validate_answer(
        draft("The company manufactures cables.", "We manufacture cables and electrical products."),
        [source],
    )
    assert withheld == 0 and len(claims) == 1
    assert claims[0]["citation"]["source_url"] == source["source_url"]
    assert claims[0]["citation"]["pdf_page"] == 7
    assert claims[0]["citation"]["published_at"] is None


def test_pdf_word_spacing_returns_the_original_source_not_an_edited_quote():
    body = "Management revi sed the guidance after the quarter."
    result = resolve_source_quote("Management revised the guidance", body)
    assert result == "Management revi sed the guidance"
    assert result in body
    assert resolve_source_quote("Management increased the guidance", body) is None


def test_quote_alignment_cannot_merge_ambiguous_numbers_into_a_claim():
    source = evidence()
    source["body"] = "Revenue was INR 1 00 crore for the quarter."
    claims, withheld = validate_answer(
        draft("Revenue was INR 100 crore.", "Revenue was INR 100 crore for the quarter."), [source]
    )
    assert not claims and withheld == 1


@pytest.mark.parametrize(
    "statement,quote,evidence_id",
    [
        ("Makes cables.", "We manufacture cables and electrical products.", "invented-id"),
        ("Makes cables.", "This quote never appeared in the actual source.", "known"),
        (
            "Revenue was INR 200 crore.",
            "Management reported revenue of INR 100 crore for the quarter.",
            "known",
        ),
    ],
)
def test_unsupported_claims_are_withheld(statement, quote, evidence_id):
    claims, withheld = validate_answer(draft(statement, quote, evidence_id), [evidence()])
    assert not claims and withheld == 1


def test_annual_report_numbers_are_gated_until_figures_validated():
    claims, withheld = validate_answer(
        draft(
            "Revenue was INR 100 crore.",
            "Management reported revenue of INR 100 crore for the quarter.",
        ),
        [evidence("annual_report")],
    )
    assert claims == [] and withheld == 1


def test_prose_number_repetition_does_not_invent_a_calculation():
    claims, withheld = validate_answer(
        draft(
            "Management reported revenue of INR 100 crore for the quarter.",
            "Management reported revenue of INR 100 crore for the quarter.",
        ),
        [evidence()],
    )
    assert len(claims) == 1 and withheld == 0
    assert not supported_numbers("Revenue was 200.", "Revenue was 100.")


def test_unvalidated_table_numbers_are_blocked_even_in_transcripts():
    source = evidence()
    source["metadata"]["contains_table_candidates"] = True
    assert (
        validate_answer(
            draft(
                "Revenue was INR 100 crore.",
                "Management reported revenue of INR 100 crore for the quarter.",
            ),
            [source],
        )[0]
        == []
    )


def test_chunks_are_page_scoped_deterministic_and_keep_metadata():
    document_id = str(uuid.uuid4())
    pages = [
        {
            "pdf_page": 2,
            "text": ("Source text with words. " * 200),
            "metadata_candidates": {"period_labels": ["March 31, 2026"]},
        },
        {"pdf_page": 3, "text": "Separate page evidence. " * 20, "metadata_candidates": {}},
    ]
    first = chunk_pages(document_id, pages, [{"pdf_page": 2}])
    assert first == chunk_pages(document_id, pages, [{"pdf_page": 2}])
    assert all(len(c["body"]) <= 1800 for c in first)
    assert all("Separate page" not in c["body"] for c in first if c["pdf_page"] == 2)
    assert first[0]["metadata"]["contains_table_candidates"] is True
    assert first[0]["metadata"]["period_labels"] == ["March 31, 2026"]


def test_narrative_chunks_use_reading_order_without_losing_layout_evidence():
    pages = [
        {
            "pdf_page": 1,
            "text": "Left column right column " * 10,
            "reading_text": "The business manufactures coffee. Its customers buy coffee products. "
            * 5,
            "metadata_candidates": {},
        }
    ]
    result = chunk_pages(str(uuid.uuid4()), pages, [])
    assert "manufactures coffee" in result[0]["body"]
    assert "Left column" not in result[0]["body"]
    assert pages[0]["text"].startswith("Left column")


def test_keyword_query_discards_question_filler_and_expands_concepts():
    assert keyword_query("what is the company?") == ""
    query = keyword_query("What is the business?")
    assert "services" in query and "products" in query and " OR " in query


def test_retrieval_passes_mandatory_company_and_optional_metadata_filters():
    class FakeStore:
        def rpc(self, name, values):
            self.name, self.values = name, values
            return []

    store = FakeStore()
    assert (
        retrieve(
            store,
            "UNPREPARED",
            "cash conversion",
            kinds=["annual_report"],
            published_before="2026-01-01T00:00:00Z",
        )
        == []
    )
    assert store.values["p_symbol"] == "UNPREPARED"
    assert store.values["p_kinds"] == ["annual_report"]
    assert store.values["p_published_before"].startswith("2026-01-01")


def test_retrieval_caps_page_and_document_repetition():
    class FakeStore:
        def rpc(self, name, values):
            return [
                {
                    "document_id": "a",
                    "pdf_page": 1,
                    "chunk_id": str(i),
                    "source_url": "https://issuer.example/source.pdf",
                }
                for i in range(20)
            ]

        def rows(self, table, **params):
            return [{"id": "a", "final_url": "https://issuer.example/source.pdf"}]

    assert len(retrieve(FakeStore(), "ANY", "business")) == 2


def test_primary_documents_cannot_target_private_networks(monkeypatch):
    import socket
    from finn.sources import validate_source_url

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
    )
    with pytest.raises(ValueError, match="private network"):
        validate_source_url("https://private.example/file.pdf")
    with pytest.raises(ValueError, match="without credentials"):
        validate_source_url("https://user:password@issuer.example/file.pdf")


def test_request_normalises_any_nse_symbol_and_rejects_urls():
    assert ResearchRequest(symbol=" m&m.ns ", question="What is the business?").symbol == "M&M"
    with pytest.raises(ValueError):
        ResearchRequest(symbol="https://internal.example", question="What is this?")
    with pytest.raises(ValueError):
        ResearchRequest(symbol="INFY", question="          ")


def test_source_refresh_reuses_answer_only_after_successful_refresh(monkeypatch):
    from finn import research

    refreshes = []

    def refreshed(store, symbol, **kwargs):
        refreshes.append(kwargs["refresh"])
        return {
            "symbol": symbol,
            "corpus_fingerprint": "same-documents",
            "source_checked_at": "new-check",
        }

    monkeypatch.setattr(research, "ensure_corpus", refreshed)

    class Store:
        def rows(self, table, **kwargs):
            assert table == "finn_research_cache"
            return [
                {
                    "id": "saved",
                    "is_public": True,
                    "created_at": "original-date",
                    "result": {"generated_at": "original-date", "claims": []},
                }
            ]

    answer = research.research_company(Store(), "INFY", research.DEFAULT_QUESTION, refresh=True)
    assert refreshes == [True]
    assert answer["cached"] is True
    assert answer["generated_at"] == "original-date"
    assert answer["source_checked_at"] == "new-check"


def test_failed_refresh_never_returns_old_cached_answer(monkeypatch):
    import pytest
    from finn import research

    def unavailable(*args, **kwargs):
        raise RuntimeError("Source unavailable")

    monkeypatch.setattr(research, "ensure_corpus", unavailable)

    class Store:
        def rows(self, *args, **kwargs):
            raise AssertionError("Must not use a cache after failed source refresh")

    with pytest.raises(RuntimeError, match="Source unavailable"):
        research.research_company(Store(), "INFY", research.DEFAULT_QUESTION, refresh=True)
