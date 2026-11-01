from copy import deepcopy
from datetime import datetime, timezone

import pytest
from finn.briefing import classify_filing
from finn.filing_details import (
    DISPLAY_VERSION,
    VERSION,
    concise,
    enrich_filings,
    format_details,
    input_hash,
    needs_extraction,
    official_pages,
    present,
    reporting_period,
)


def filing(description="Financial Results Updates", **values):
    return {
        "id": "one",
        "symbol": "TEST",
        "company_name": "Test Limited",
        "title": description,
        "description": description,
        "source_url": "https://nsearchives.nseindia.com/corporate/test.pdf",
        "published_at": "2026-10-31T09:00:00+00:00",
        "category": "results",
        "priority": 3,
        **values,
    }


def test_scheduled_tenure_and_unexpected_resignation_have_different_priorities():
    assert classify_filing(
        "Prof. Rajiv Lal completed his 2nd term as an Independent Director of the Company."
    )[:2] == ("management_change", 1)
    assert classify_filing("Resignation of Chief Executive Officer")[:2] == ("management_change", 3)
    assert (
        classify_filing(
            "An Independent Director completed his term. Resignation of Chief Executive Officer."
        )[1]
        == 3
    )


def test_recording_and_presentation_are_not_results_even_when_results_are_mentioned():
    recording = (
        "Audio recording of discussion on Unaudited Financial Results of the company is available."
    )
    assert classify_filing(recording)[:2] == ("earnings_call", 1)
    row = filing(recording, title="Analysts/Institutional Investor Meet/Con. Call Updates")
    stale = {
        **present(row),
        "category": "results",
        "actual_results": True,
        "event_key": "results:2026-09-30",
    }
    fresh = format_details(row, stale)
    assert (
        fresh["category"] == "earnings_call"
        and not fresh["actual_results"]
        and fresh["event_key"] is None
    )
    assert (
        classify_filing("Investor Presentation on quarterly financial results")[0]
        == "earnings_call"
    )


def test_debt_table_cannot_be_promoted_to_narrative_summary():
    row = filing("Confirmation of Redemption/Payment of Interest and Principal")
    raw = "Record date for redemption: ISIN Date of allotment Amount crore Due Date Actual Date of Payment INE081A14HI3 August 3, 2026 750 October 30, 2026."
    fresh = format_details(
        row,
        {**present(row), "summary": raw, "evidence": [{"quote": raw, "kind": "official_document"}]},
    )
    assert (
        fresh["summary"] is None and fresh["status"] == "headline_only" and fresh["evidence"] == []
    )


def test_results_board_authorisation_keeps_amount_and_does_not_claim_funds_raised():
    text = "In continuation of our letter dated October 27, 2026, the Board has, inter alia:1. approved the unaudited Financial Results for the quarter ended September 30, 2026; and2. passed an enabling resolution authorising the issuance of debentures up to Rs. 15,000 crore on private placement basis."
    row = filing(text, title="Outcome of Board Meeting")
    fresh = format_details(row, present(row))
    assert "15,000 crore" in fresh["summary"] and "enabling resolution" in fresh["summary"]
    assert "debt-issue authorisation" in fresh["headline"] and "raised" not in fresh["summary"]


def test_results_narrative_has_period_page_and_no_inferred_financial_rows():
    row = filing()
    text = "The Board approved the Unaudited Standalone and Consolidated Financial Results for the quarter and half year ended 30 September 2026. Further attachments follow."
    result = present(row, pages=[{"pdf_page": 1, "text": text}])
    assert result["period_end"] == "2026-09-30" and result["event_key"] == "results:2026-09-30"
    assert result["actual_results"] and result["evidence"][0]["pdf_page"] == 1
    assert result["evidence"][0]["quote"] in text
    assert "Revenue" not in str(result) and "PAT" not in str(result)


def test_period_and_native_extraction_do_not_merge_business_events_into_results():
    row = filing(
        "Commercial operation of a solar plant for the quarter ended 30 September 2026",
        category="business_update",
        priority=2,
    )
    result = present(row)
    assert result["period_end"] == "2026-09-30" and result["event_key"] is None


def test_din_is_retained_in_support_but_removed_from_summary_and_tenure_group_is_specific():
    body = "Prof. Rajiv Lal (DIN: 09360601) completed his 2nd term as an Independent Director of the Company on October 31, 2026."
    result = present(filing(body, title="Cessation", category="management_change"))
    assert "09360601" not in result["summary"] and "09360601" in result["evidence"][0]["quote"]
    assert result["priority"] == 1 and result["event_key"] == "tenure:09360601:2026-10-31"


def test_multi_person_disclosure_is_not_given_a_single_tenure_identity():
    text = "Prof. Rajiv Lal (DIN: 09360601) completed his 2nd term as an Independent Director of the Company on October 31, 2026. Mr. Other Person (DIN: 12345678) also changed roles."
    assert present(filing(text))["event_key"] is None


def test_generic_headline_abstains_without_details_instead_of_repeating_advice():
    result = present(filing())
    assert result["status"] == "headline_only" and result["summary"] is None
    assert not result["actual_results"] and result["evidence"] == []


def test_presentation_update_reuses_cited_text_and_preserves_source_check_time():
    row = filing()
    quote = "Approved the Unaudited Financial Results for the quarter ended 30 September 2026. The next sentence is not needed."
    result = present(
        row,
        pages=[{"pdf_page": 1, "text": quote}],
        source={"method": "native_pdf_text", "fetched_at": "2026-10-31T09:00:00+00:00"},
    )
    old = deepcopy(result)
    refreshed = format_details(row, result)
    assert refreshed["summary"] == quote.split(". ")[0] + "."
    assert refreshed["source"] == old["source"] and refreshed["evidence"] == old["evidence"]
    assert refreshed["display_version"] == DISPLAY_VERSION


def test_concise_summary_preserves_names_and_uses_visible_truncation():
    text = "Prof. Rajiv Lal completed a scheduled term as Independent Director on October 31, 2026. Accordingly, another role ended."
    assert concise(text).startswith("Prof. Rajiv Lal") and "Accordingly" not in concise(text)
    assert concise("A " * 350).endswith("…")


@pytest.mark.parametrize(
    "text, expected",
    [
        ("quarter ended 30 September 2026", "2026-09-30"),
        ("year ended September 30, 2026", "2026-09-30"),
        ("quarter ended 31 February 2026", None),
        ("Q2FY27 filename only", None),
    ],
)
def test_reporting_period_requires_an_explicit_valid_date(text, expected):
    assert reporting_period(text) == expected


class Store:
    def __init__(self, rows):
        self.data, self.patches = rows, []

    def rows(self, table, **kwargs):
        return self.data

    def patch(self, table, values, **kwargs):
        self.patches.append(values)

    def put_pdf(self, *args):
        pass


def test_unchanged_cached_filings_do_not_download_or_repeat_extraction(monkeypatch):
    row = filing()
    row["enrichment"] = format_details(row, present(row))
    store = Store([row])
    monkeypatch.setattr(
        "finn.filing_details.official_pages",
        lambda *args: pytest.fail("Repeated unchanged document extraction"),
    )
    assert enrich_filings(store)["downloads"] == 0 and store.patches == []


def test_download_failure_keeps_original_and_honest_headline_fallback(monkeypatch):
    row = filing()
    monkeypatch.setattr(
        "finn.filing_details.official_pages",
        lambda *args: (_ for _ in ()).throw(ValueError("Access denied")),
    )
    store = Store([row])
    result = enrich_filings(store)
    assert result["unavailable"] == 1
    detail = store.patches[0]["enrichment"]
    assert (
        detail["status"] == "headline_only"
        and detail["limitation"]
        and row["source_url"].startswith("https://")
    )


def test_document_failure_is_cached_with_bounded_retry_but_changed_input_retries():
    row = filing()
    row["enrichment"] = {
        "version": VERSION,
        "input_hash": input_hash(row),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "limitation": "Failed download",
    }
    assert not needs_extraction(row)
    row["description"] = "Revised filing"
    assert needs_extraction(row)


def test_non_exchange_source_is_not_fetched():
    with pytest.raises(ValueError, match="official exchange"):
        official_pages(None, "https://example.com/private.pdf")
