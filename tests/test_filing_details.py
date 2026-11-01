from copy import deepcopy
from datetime import datetime, timezone

import pytest
from finn.briefing import classify_filing
from finn.filing_details import (
    DISPLAY_VERSION,
    VERSION,
    complete_passage,
    concise,
    dividend_reference,
    enrich_filings,
    format_details,
    input_hash,
    needs_extraction,
    official_pages,
    present,
    recording_reference,
    reporting_period,
)


def test_recordings_group_only_with_explicit_call_date_and_shared_recording_link():
    # Manually checked against NTPC's original 31 October XML/PDF pair.
    fields = [
        {"field": "DateOfCallForAudioRecording", "text": "2026-10-31"},
        {
            "field": "WeblinkOfAudioRecording",
            "text": "https://ntpc.co.in/investors/conference-call",
        },
    ]
    pages = [
        {
            "pdf_page": 1,
            "text": "Audio Recording of Earnings Conference Call. A conference call was held on 31 October 2026. Link for accessing Audio Recording: https://www.ntpc.co.in/investors/conference-call",
        }
    ]
    structured, evidence = recording_reference(fields)
    document, quotes = recording_reference(pages)
    assert structured["event_key"] == document["event_key"]
    assert all(q["quote"] in pages[0]["text"] for q in quotes)
    assert evidence[0]["field"] == "DateOfCallForAudioRecording"
    assert (
        recording_reference([{**fields[0], "text": "2026-10-30"}, fields[1]])[0]["event_key"]
        != document["event_key"]
    )
    assert recording_reference([fields[1]])[0] is None
    assert recording_reference([*fields, {**fields[0], "text": "2026-10-30"}])[0] is None
    assert (
        recording_reference(
            [
                {
                    "pdf_page": 1,
                    "text": pages[0]["text"]
                    + " Another conference call was held on 30 October 2026.",
                }
            ]
        )[0]
        is None
    )
    assert recording_reference([{**fields[0], "field": "DateOfReport"}, fields[1]])[0] is None
    assert recording_reference([fields[0], {**fields[1], "text": "javascript:alert(1)"}])[0] is None


def test_tenure_additional_roles_have_exact_support_and_do_not_repeat_cessation():
    text = "Prof. Rajiv Lal (DIN: 09360601) completed his 2nd term as an Independent Director of the Company on October 31, 2026, and consequently he has ceased to be a Director of the Company w.e.f. the end of business hours of said date. Accordingly, he has also ceased to be a Director of KPIT Technologies Inc., material unlisted subsidiary of the Company and member of Nomination & Remuneration (HR) Committee of the Company, effective from said date."
    row = filing(text, title="Cessation")
    result = format_details(row, present(row, pages=[{"pdf_page": 1, "text": text}]))
    assert result["effective_date"] == "2026-10-31"
    assert len(result["additional_details"]) == 1
    assert "Nomination & Remuneration" in result["additional_details"][0]
    assert any(
        e["quote"] == result["additional_details"][0] and e["pdf_page"] == 1
        for e in result["evidence"]
    )
    assert "consequently" not in result["summary"]
    assert "close of business" in result["summary"]
    ambiguous = present(
        row, pages=[{"pdf_page": 1, "text": text + " Other director DIN: 12345678."}]
    )
    assert ambiguous["additional_details"] == [] and ambiguous["effective_date"] is None


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


def test_summary_cleaning_preserves_complete_text_without_display_limits():
    text = "Prof. Rajiv Lal completed a scheduled term as Independent Director on October 31, 2026. Accordingly, another role ended."
    assert concise(text) == text
    assert concise("A " * 350) == ("A " * 350).strip()
    assert concise("Outcome of Board Meeting held on 31-Oct-2026 for Dividend").endswith(
        "for Dividend"
    )
    assert "Accordingly" not in complete_passage(text)
    assert (
        complete_passage("Approved the financial results. Further attachments are encl")
        == "Approved the financial results."
    )
    assert complete_passage("Only a partial phrase without a sentence") is None


@pytest.mark.parametrize(
    "source",
    [
        "Outcome of Board Meeting held on 31-Oct-2026 for Dividend",
        "General Updates- Operational & Financial Snapshot for Quarter & Half Year ended 30 September 2026",
    ],
)
def test_clipped_legacy_summary_recovers_from_preserved_feed_without_fetching(source):
    row = filing(source, title="General Updates")
    original = present(row)
    original["summary"] = source.rsplit(" ", 1)[0] + "\u2026"
    updated = format_details(row, original)
    assert updated["summary"] == source
    assert not updated["summary_incomplete"]
    incomplete = format_details({**row, "description": source + "..."}, original)
    assert incomplete["summary"].endswith("...") and incomplete["summary_incomplete"]


def test_debt_topics_are_distinct_from_results_and_each_other():
    keys = []
    for title in [
        "Security Cover",
        "Statement of utilization of issue proceeds",
        "Disclosure under Regulation 52(4)",
    ]:
        row = filing(title)
        original = {
            **present(row),
            "period_end": "2026-09-30",
            "event_key": "results:2026-09-30",
            "actual_results": True,
            "source": {"sha256": "a" * 64},
        }
        result = format_details(row, original)
        assert not result["actual_results"] and result["category"] == "capital"
        assert "results:" not in result["event_key"]
        assert "Supporting debt disclosure within" not in result["summary"]
        keys.append(result["event_key"])
    assert len(set(keys)) == 3


def test_dividend_link_requires_type_and_record_date_and_keeps_exact_support():
    text = 'The Board declared the First Interim Dividend. The Company has fixed 6 November 2026 as the "record date".'
    reference, quotes = dividend_reference([{"pdf_page": 1, "text": text}])
    assert reference["event_key"] == "dividend:interim:2026-11-06"
    assert all(q["quote"] in text and q["pdf_page"] == 1 for q in quotes)
    fields = [
        {
            "field": "WhetherDeclarationOfInterimDividendOrRecommendationOfFinalDividendApprovedByTheBoard",
            "text": "Yes",
        },
        {"field": "FirstTypeOfDividend", "text": "Interim"},
        {"field": "RecordDateOfInterimDividend", "text": "2026-11-06"},
    ]
    assert dividend_reference(fields)[0] == reference
    assert dividend_reference(fields[:-1])[0] is None
    assert dividend_reference([*fields, {**fields[-1], "text": "2026-12-06"}])[0] is None
    assert dividend_reference([{**fields[0], "text": "No"}, *fields[1:]])[0] is None


def test_short_structured_fields_are_usable_source_data(monkeypatch):
    row = filing(
        "Outcome of Board Meeting held on 31-Oct-2026 for Dividend",
        title="Outcome of Board Meeting-XBRL",
        source_url="https://nsearchives.nseindia.com/test.xml",
    )
    fields = [
        {
            "field": "WhetherDeclarationOfInterimDividendOrRecommendationOfFinalDividendApprovedByTheBoard",
            "text": "Yes",
        },
        {"field": "FirstTypeOfDividend", "text": "Interim"},
        {"field": "RecordDateOfInterimDividend", "text": "2026-11-06"},
    ]
    monkeypatch.setattr(
        "finn.filing_details.official_pages",
        lambda *args: (b"<xml/>", fields, {"url": row["source_url"], "method": "exchange_xml"}),
    )
    store = Store([row])
    assert enrich_filings(store)["unavailable"] == 0
    detail = store.patches[-1]["enrichment"]
    assert detail["dividend_reference"]["record_date"] == "2026-11-06"
    assert detail["limitation"] is None
    assert not needs_extraction({**row, "enrichment": detail})


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


def test_topic_refresh_reuses_shared_private_pdf_and_original_fetch_time(monkeypatch):
    import hashlib
    import io

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buffer = io.BytesIO()
    writer.write(buffer)
    data = buffer.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    source = {
        "method": "native_pdf_text",
        "sha256": digest,
        "url": "https://nsearchives.nseindia.com/test.pdf",
        "fetched_at": "2026-10-31T10:00:00+00:00",
        "pages_scanned": 1,
        "total_pages": 1,
    }
    rows = [
        filing(title, id=str(i))
        for i, title in enumerate(["Security Cover", "Statement of utilization of issue proceeds"])
    ]
    for row in rows:
        row["enrichment"] = format_details(row, present(row, source=source))
        row["enrichment"].pop("topic_version")
    store, reads = Store(rows), []
    store.get_pdf = lambda *args: reads.append(args) or data
    store.put_pdf = lambda *args: pytest.fail("Cached PDFs must not be uploaded again")
    monkeypatch.setattr(
        "finn.filing_details.official_pages",
        lambda *args: pytest.fail("Unnecessary source download"),
    )
    result = enrich_filings(store, refresh_topics=True)
    assert result["updated"] == 2 and result["downloads"] == 0 and result["reused_documents"] == 2
    assert len(reads) == 1
    assert all(
        update["enrichment"]["source"]["fetched_at"] == source["fetched_at"]
        for update in store.patches
    )


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
