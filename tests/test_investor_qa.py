from copy import deepcopy
from decimal import Decimal

from finn.financial_insights import with_performance
from finn.management_readings import concrete_comparison
from finn.question_plan import (
    assess_coverage,
    focused_text,
    plan_question,
    relevance,
    retrieve_planned,
)


def test_company_name_products_is_not_an_extra_requested_topic():
    plan = plan_question(
        "What affects CCL Products' profitability and what has management said about demand, production capacity and future growth?"
    )
    assert [p["id"] for p in plan] == ["profitability", "demand", "capacity", "growth"]


def test_volume_guidance_does_not_satisfy_a_demand_question():
    claim = {
        "statement": "Management guides for volume growth of 15%.",
        "citation": {"quote": "We expect volume growth of 15%."},
    }
    coverage = assess_coverage(
        plan_question("What has management said about demand and future growth?"), [claim], []
    )
    assert coverage[0]["status"] == "missing" and coverage[1]["status"] == "covered"


def test_customer_sectors_do_not_substitute_for_services_offered():
    claim = {
        "statement": "The company serves clients in financial services and manufacturing.",
        "citation": {
            "quote": "Our clients include financial services and manufacturing enterprises."
        },
    }
    assert (
        assess_coverage(plan_question("Explain the core business."), [claim], [])[0]["status"]
        == "missing"
    )


def test_guidance_does_not_substitute_for_profitability_drivers():
    claim = {
        "statement": "Management expects volume and EBITDA growth.",
        "citation": {"quote": "We expect volume and EBITDA growth."},
    }
    assert (
        assess_coverage(plan_question("What affects profitability?"), [claim], [])[0]["status"]
        == "missing"
    )


def test_recognition_as_an_industry_leader_is_not_accounting_detail():
    text = "The company was recognized as an industry leader in cybersecurity services."
    assert focused_text("Explain its business model.", text) == text


def test_qualitative_segments_are_not_verified_relative_contributions():
    c = {
        "statement": "Automotive and farm equipment contribute through sales of vehicles and tractors.",
        "citation": {"quote": "Our automotive and farm segments sell vehicles and tractors."},
    }
    note = assess_coverage(
        plan_question("Explain segments and their relative contribution."), [c], []
    )[-1]
    assert note["status"] != "covered" and "numerical" in note["note"]


def test_commercial_focus_retains_original_contiguous_source_and_contract_types():
    body = "The Group derives revenues from consulting and software services. Contracts with customers are either time-and-material, unit of work or fixed-price. Revenue is recognized when performance obligations are satisfied."
    focused = focused_text("Explain its business model and how it generates revenue.", body)
    assert focused in body and "fixed-price" in focused and "consulting" in focused
    assert "recognized" not in focused
    assert focused_text("Explain revenue recognition.", body) == body
    assert relevance({"body": body}, "commercial", "business model") > 0


def test_planned_search_keeps_metadata_scope_and_does_not_add_embeddings(monkeypatch):
    from finn import question_plan

    calls = []

    def search(*args, **kw):
        calls.append(kw)
        return {"evidence": []}

    monkeypatch.setattr(question_plan, "retrieve_with_diagnostics", search)
    p = plan_question("What has management said about profitability, demand, capacity and growth?")
    retrieve_planned(
        None,
        "TEST",
        "What has management said about profitability, demand, capacity and growth?",
        {"evidence": []},
        p,
        document_ids=["original-document"],
        metadata_filter={"scope": "reviewed"},
        published_before="2026-10-31",
    )
    assert len(calls) == 4
    assert all(
        c["strategy"] == "keyword"
        and c["document_ids"] == ["original-document"]
        and c["metadata_filter"] == {"scope": "reviewed"}
        and c["kinds"] == ["transcript"]
        for c in calls
    )


def financial():
    rows = []
    for i, (metric, current, base) in enumerate(
        [("Revenue", "120", "100"), ("PBT", "10", "20"), ("PAT", "5", "10")]
    ):
        delta = Decimal(current) - Decimal(base)
        rows.append(
            {
                "metric": metric,
                "figures": {
                    "latest": {"claim_index": i * 2, "definition": "revenue_from_operations"},
                    "year_ago": {"claim_index": i * 2 + 1},
                },
                "yoy": {"absolute": str(delta), "percent": str(delta / Decimal(base) * 100)},
                "qoq": {"absolute": None, "percent": None},
            }
        )
    return {
        "claims": [],
        "financial_results": {
            "bases": {"consolidated": {"rows": rows, "unit": "million", "currency": "INR"}},
            "periods": {"latest": "2026-09-30", "year_ago": "2025-09-30"},
        },
    }


def test_financial_interpretation_uses_only_valid_changes_and_preserves_original():
    original = financial()
    before = deepcopy(original)
    r = with_performance(original)
    note = r["financial_results"]["bases"]["consolidated"]["performance"][0]
    assert "Revenue rose by 20.0%" in note["statement"]
    assert "PBT fell by 50.0%" in note["statement"] and "PAT fell by 50.0%" in note["statement"]
    assert "did not translate" in note["statement"] and "due to" not in note["statement"]
    assert note["claim_indices"] == [0, 1, 2, 3, 4, 5] and original == before


def test_missing_or_nonpositive_base_does_not_invent_percentages_or_metrics():
    r = financial()
    v = r["financial_results"]["bases"]["consolidated"]
    v["rows"] = v["rows"][:1]
    v["rows"][0]["yoy"] = {"absolute": "120", "percent": None}
    note = with_performance(r)["financial_results"]["bases"]["consolidated"]["performance"][0]
    assert (
        "INR 120 million" in note["statement"]
        and "%" not in note["statement"]
        and "PAT" not in note["statement"]
    )


def pair():
    a = {
        "statement": "An abstract annual target.",
        "citation": {
            "id": "earlier",
            "quote": "EBITDA 20.5 to 21.2. This is about FY27.",
            "source_identifiers": ["FY26"],
        },
    }
    b = {
        "statement": "Some quarterly metrics.",
        "citation": {
            "id": "later",
            "quote": "For this quarter, EBITDA was at 17.2%, EBIT at 12.3% and PAT at INR 1.17 billion.",
            "source_identifiers": ["FY27", "Q1"],
        },
    }
    synthesis = {"statement": "Abstract transition.", "citation": a["citation"]}
    return {
        "id": "original-parent",
        "claims": [a, b, synthesis],
        "comparison": {
            "earlier": a,
            "later": b,
            "verdict": "not_yet_assessable",
            "analysis_claims": [synthesis],
        },
    }


def test_target_and_reported_figures_are_concrete_without_inventing_target_units():
    original = pair()
    before = deepcopy(original)
    r = concrete_comparison(original)
    assert "20.5 to 21.2" in r["claims"][0]["statement"] and "%" not in r["claims"][0]["statement"]
    assert (
        "17.2%" in r["claims"][1]["statement"] and "INR 1.17 billion" in r["claims"][1]["statement"]
    )
    assert (
        "Q1 FY27" in r["claims"][1]["statement"]
        and r["comparison"]["verdict"] == "not_yet_assessable"
    )
    assert r["id"] == "original-parent" and original == before and concrete_comparison(r) == r


def test_working_reaffirmation_with_explicit_percentage_is_unchanged():
    r = pair()
    r["comparison"]["earlier"]["citation"]["quote"] = (
        "We guide for annual volume growth of 15% and similar EBITDA growth."
    )
    r["comparison"]["verdict"] = "reaffirmed"
    assert concrete_comparison(r) == r


def test_disclosure_requires_the_explicit_current_quarter():
    from finn.disclosed_context import quarter_in_quote

    assert quarter_in_quote(
        "A charge was recognised for the quarter ended September 30, 2026.", "2026-09-30"
    )
    assert not quarter_in_quote(
        "A charge was recognised for the year ended March 31, 2026.", "2026-09-30"
    )
    assert not quarter_in_quote(
        "A charge was recognised for the quarter ended June 30, 2026.", "2026-09-30"
    )


def test_disclosed_context_keeps_current_notes_separate_from_older_items():
    from finn.disclosed_context import disclosed_paragraphs

    text = "a) Acquisition-related costs were recorded for the quarter ended June 30, 2026. b) A litigation settlement agreement was signed and a tax benefit recorded for the quarter ended September 30, 2026."
    found = list(disclosed_paragraphs(text, "2026-09-30"))
    assert len(found) == 1 and "litigation" in found[0][0]
    assert "June" not in found[0][1] and "September" in found[0][1]


def test_additive_note_preservation_never_replaces_existing_source_pages(monkeypatch):
    from finn import disclosed_context as context

    monkeypatch.setattr(
        context,
        "native_page_texts",
        lambda *args: ["Original statement text", "Original notes text"],
    )
    writes = []

    class Store:
        def get_pdf(self, *args):
            return b"hash-checked-original"

        def rows(self, *args, **kwargs):
            return [{"pdf_page": 1}]

        def upsert(self, table, rows, **kwargs):
            writes.append((table, rows))

        def patch(self, *args, **kwargs):
            pass

        def delete(self, *args, **kwargs):
            raise AssertionError("Old evidence cannot be deleted")

    doc = {
        "id": "00000000-0000-0000-0000-000000000001",
        "storage_path": "original.pdf",
        "sha256": "checked",
        "extraction_notes": {},
    }
    context.preserve_missing_pages(Store(), doc)
    assert all(row["pdf_page"] == 2 for table, rows in writes for row in rows)
    assert doc["extraction_notes"]["financial_native_pages_version"] == 1


def test_failed_focused_search_keeps_the_base_evidence_and_records_failure(monkeypatch):
    from finn import question_plan
    from finn.services import DependencyError

    def failed(*args, **kw):
        raise DependencyError("source unavailable")

    monkeypatch.setattr(question_plan, "retrieve_with_diagnostics", failed)
    source = {
        "chunk_id": "known",
        "document_id": "same-company",
        "pdf_page": 3,
        "body": "Management described demand and orders.",
    }
    result = retrieve_planned(
        None, "TEST", "What is demand?", {"evidence": [source]}, plan_question("What is demand?")
    )
    assert result["evidence"] == [source] and result["question_plan_failures"] == [
        "Demand and orders"
    ]
