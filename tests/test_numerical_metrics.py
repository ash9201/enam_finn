import io
import uuid
from decimal import Decimal

import pytest
from finn import metric_research
from finn.metric_calculations import calculate
from finn.metric_evidence import Fact, extract_metric_cells, extract_metric_prose, issuer_verified
from finn.metric_registry import REGISTRY, FinancialIntent, financial_intent
from finn.metric_research import complete_numerical_answer, select_results
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas


@pytest.mark.parametrize(
    "question,key",
    [
        ("debt to equity ratio", "debt_equity"),
        ("D/E", "debt_equity"),
        ("debt-equity", "debt_equity"),
        ("What is the debt/equity ratio?", "debt_equity"),
        ("ROE of Infosys", "roe"),
        ("return on equity", "roe"),
        ("P/E", "pe"),
        ("current ratio", "current_ratio"),
        ("revenue growth", "revenue_growth"),
        ("how much debt does this company have?", "debt"),
        ("net profit margin", "net_margin"),
        ("total borrowings", "debt"),
        ("quarterly EPS", "eps"),
        ("what's their interest coverage?", "interest_coverage"),
        ("net-debt-to-equity", "net_debt_equity"),
        ("EV/EBITDA", "ev_ebitda"),
        ("forward P/E", "forward_pe"),
        ("CET1 ratio", "cet1"),
        ("gross NPA ratio", "gnpa_ratio"),
        ("annualized premium equivalent", "ape"),
        ("ARPU", "arpu"),
    ],
)
def test_aliases_request_actual_figures(question, key):
    assert financial_intent(question).metrics == (key,)


@pytest.mark.parametrize(
    "question",
    [
        "Explain what ROE means",
        "What does ROE mean?",
        "Define current ratio",
        "How is return on equity calculated?",
        "Explain debt to equity",
        "How does management manage debt risk?",
        "Describe the operating business",
        "Who is the CFO of Infosys?",
        "What is employee turnover?",
        "What is the difference between ROE and ROCE?",
    ],
)
def test_conceptual_questions_remain_in_normal_research(question):
    assert financial_intent(question) is None


def test_intent_period_basis_and_multiple_metrics():
    intent = financial_intent("Consolidated ROE and current ratio for FY2025-26")
    assert intent.metrics == ("roe", "current_ratio") and intent.basis == "consolidated"
    assert intent.years == (2026,)
    assert len(financial_intent("How profitable is the company?").metrics) > 1
    assert len(REGISTRY) >= 130
    assert REGISTRY["pe"].support == "dated_reported_only"
    assert REGISTRY["dscr"].support == "reported_only"
    assert financial_intent("quarterly EPS Q1FY27").period_ends == ("2026-06-30",)
    assert financial_intent("D/E at 31 March 2026").period_ends == ("2026-03-31",)
    assert financial_intent("Explain ROE and give its actual value").metrics == ("roe",)
    assert financial_intent("How does the company generate revenue?") is None


def fact(
    key,
    value,
    *,
    period="2026-03-31",
    basis="consolidated",
    unit="crore",
    currency="INR",
    kind="year",
    entity="INE123A01016",
    definition=None,
):
    return Fact(
        key,
        Decimal(value),
        unit,
        currency,
        period,
        kind,
        basis,
        entity,
        {
            "id": str(uuid.uuid4()),
            "quote": "Original source cell",
            "metric_evidence": {"verification": "native_pdf_geometry"},
        },
        definition or key,
        raw_value=value,
    )


def test_verified_arithmetic_units_and_original_inputs():
    inputs = [fact("debt", "4500", unit="million"), fact("equity", "1000")]
    result, reason = calculate("debt_equity", inputs, "2026-03-31", "consolidated", "INE123A01016")
    assert reason is None and result.value == Decimal(".45") and result.unit == "times"
    assert result.inputs == inputs and result.method == "calculated" and result.formula
    assert result.citation is inputs[0].citation


@pytest.mark.parametrize(
    "changed",
    [
        {"basis": "standalone"},
        {"period": "2025-03-31"},
        {"currency": "USD"},
        {"entity": "OTHER"},
    ],
)
def test_incompatible_inputs_never_form_ratios(changed):
    inputs = [fact("debt", "45"), fact("equity", "100", **changed)]
    assert calculate("debt_equity", inputs, "2026-03-31", "consolidated", "INE123A01016")[0] is None


@pytest.mark.parametrize("denominator", ["0", "-10"])
def test_zero_negative_denominators_rejected(denominator):
    f, reason = calculate(
        "current_ratio",
        [fact("current_assets", "100"), fact("current_liabilities", denominator)],
        "2026-03-31",
        "consolidated",
        "INE123A01016",
    )
    assert f is None and "zero or negative" in reason


def test_margins_net_debt_interest_and_cash_flow():
    fs = [
        fact("pat", "-10"),
        fact("revenue", "100"),
        fact("debt", "45"),
        fact("cash", "60"),
        fact("ebit", "20"),
        fact("interest_expense", "5"),
        fact("cfo", "100"),
        fact("cash_capex", "-30"),
    ]
    expected = {"net_margin": "-10", "net_debt": "-15", "interest_coverage": "4", "fcf": "70"}
    for key, value in expected.items():
        assert calculate(key, fs, "2026-03-31", "consolidated", "INE123A01016")[0].value == Decimal(
            value
        )
    fs[-1].value = Decimal(30)
    assert calculate("fcf", fs, "2026-03-31", "consolidated", "INE123A01016")[0] is None


def test_flow_ratios_reject_unknown_or_point_in_time_durations():
    fs = [fact("pat", "10", kind="point"), fact("revenue", "100")]
    value, reason = calculate("net_margin", fs, "2026-03-31", "consolidated", "INE123A01016")
    assert value is None and "duration" in reason


def test_average_balances_and_complete_period_growth():
    fs = [
        fact("profit_owners", "20"),
        fact("equity", "120", definition="owners_equity", kind="point"),
        fact("equity", "80", period="2025-03-31", definition="owners_equity", kind="point"),
        fact("revenue", "120"),
        fact("revenue", "100", period="2025-03-31"),
    ]
    assert calculate("roe", fs, "2026-03-31", "consolidated", "INE123A01016")[0].value == 20
    assert (
        calculate("revenue_growth", fs, "2026-03-31", "consolidated", "INE123A01016")[0].value == 20
    )
    fs[0].period_kind = "quarter"
    assert calculate("roe", fs, "2026-03-31", "consolidated", "INE123A01016")[0] is None
    fs[-1].period_kind = "stub"
    assert calculate("revenue_growth", fs, "2026-03-31", "consolidated", "INE123A01016")[0] is None


def test_roce_uses_average_capital_and_growth_has_positive_base():
    fs = [
        fact("ebit", "26"),
        fact("total_assets", "200", kind="point"),
        fact("current_liabilities", "50", kind="point"),
        fact("total_assets", "150", period="2025-03-31", kind="point"),
        fact("current_liabilities", "40", period="2025-03-31", kind="point"),
    ]
    result, _ = calculate("roce", fs, "2026-03-31", "consolidated", "INE123A01016")
    assert result.value == 20 and len(result.inputs) == 5
    for baseline in ["0", "-100"]:
        assert (
            calculate(
                "revenue_growth",
                [fact("revenue", "120"), fact("revenue", baseline, period="2025-03-31")],
                "2026-03-31",
                "consolidated",
                "INE123A01016",
            )[0]
            is None
        )


def test_calculated_sources_keep_same_page_input_cells_separate():
    from finn.metric_research import attach_evidence, fact_view

    fs = [fact("debt", "45"), fact("equity", "100")]
    fs[1].citation["id"] = fs[0].citation["id"]
    result, _ = calculate("debt_equity", fs, "2026-03-31", "consolidated", "INE123A01016")
    claims = []
    view = fact_view(result)
    attach_evidence(result, view, claims)
    assert view["claim_indices"] == [0, 1] and len(claims) == 2
    assert view["inputs"][0]["claim_index"] == 0 and view["inputs"][1]["claim_index"] == 1
    assert "Total borrowings" in claims[0]["statement"] and "equity" in claims[1]["statement"]


def test_explicit_year_growth_can_use_prior_year_without_exposing_other_period():
    rows = select_results(
        FinancialIntent(("revenue_growth",), years=(2026,)),
        [fact("revenue", "120"), fact("revenue", "100", period="2025-03-31")],
        {"isin": "INE123A01016", "name": "Acme Limited"},
    )
    assert len(rows) == 1 and Decimal(rows[0]["value"]) == 20


def test_banks_and_unverified_numbers_do_not_use_industrial_formulas():
    fs = [fact("debt", "45"), fact("equity", "100")]
    assert (
        calculate(
            "debt_equity", fs, "2026-03-31", "consolidated", "INE123A01016", sector="financial"
        )[0]
        is None
    )
    fs[0].citation["metric_evidence"] = {}
    assert calculate("debt_equity", fs, "2026-03-31", "consolidated", "INE123A01016")[0] is None


def test_related_ratios_are_not_silently_substituted():
    from finn.metric_evidence import compatible_unit

    assert not compatible_unit("revenue", "%")
    assert not compatible_unit("eps", "%")
    assert compatible_unit("ronw", "%") and compatible_unit("interest_service_coverage", "times")
    assert financial_intent("Return on net worth").metrics == ("ronw",)
    assert financial_intent("Interest service coverage ratio").metrics == (
        "interest_service_coverage",
    )
    fs = [
        fact("ronw", "20", unit="%", currency=None),
        fact("interest_service_coverage", "5", unit="times", currency=None),
    ]
    assert calculate("roe", fs, "2026-03-31", "consolidated", "INE123A01016")[0] is None
    assert (
        calculate("interest_coverage", fs, "2026-03-31", "consolidated", "INE123A01016")[0] is None
    )


def test_adjusted_and_forward_definitions_do_not_become_standard_values():
    from finn.metric_evidence import row_metric

    assert row_metric("EBITDA (adjusted)", "") == "adjusted_ebitda"
    assert row_metric("P/E (forward)", "") == "forward_pe"
    intent = financial_intent("adjusted PAT and EBITDA")
    assert intent.unsupported_variants == ("pat",)
    results = select_results(
        intent,
        [fact("pat", "10"), fact("ebitda", "20")],
        {"isin": "INE123A01016", "name": "Acme Limited"},
    )
    assert results[0]["status"] == "unavailable" and results[1]["status"] == "verified"
    assert financial_intent("EBITDA and adjusted EBITDA").unsupported_variants == ()


def test_multiple_quarters_in_one_year_are_all_returned_or_explicitly_missing():
    from dataclasses import replace

    intent = replace(
        financial_intent("D/E"),
        period_ends=("2026-06-30", "2026-09-30", "2026-12-31"),
        frequency="quarter",
    )
    facts = [
        fact("debt_equity", "0.2", period="2026-06-30", kind="point", unit="times", currency=None),
        fact("debt_equity", "0.3", period="2026-09-30", kind="point", unit="times", currency=None),
    ]
    results = select_results(intent, facts, {"isin": "INE123A01016", "name": "Acme Limited"})
    assert {r["period_end"] for r in results if r["status"] == "verified"} == {
        "2026-06-30",
        "2026-09-30",
    }
    assert results[-1]["requested_period_ends"] == ["2026-12-31"]


def test_reported_value_preferred_conflicts_not_silently_resolved():
    fs = [
        fact("debt_equity", ".38", unit="times", currency=None),
        fact("debt", "45"),
        fact("equity", "100"),
    ]
    assert calculate("debt_equity", fs, "2026-03-31", "consolidated", "INE123A01016")[0] is fs[0]
    fs.append(fact("debt_equity", ".9", unit="times", currency=None))
    result, reason = calculate("debt_equity", fs, "2026-03-31", "consolidated", "INE123A01016")
    assert result is None and "Conflicting" in reason


def test_multiple_metrics_have_explicit_missing_results_and_intent_validation():
    company = {"isin": "INE123A01016", "name": "Acme Industries Limited"}
    intent = FinancialIntent(("debt_equity", "roic"), basis="consolidated", years=(2026,))
    rows = select_results(
        intent, [fact("debt_equity", ".45", unit="times", currency=None)], company
    )
    assert [r["status"] for r in rows] == ["verified", "unavailable"]
    assert complete_numerical_answer(intent, rows)
    assert not complete_numerical_answer(
        intent,
        [
            {
                "id": "debt_equity",
                "status": "verified",
                "statement": "Monitors its capital structure.",
            }
        ],
    )


def pdf_fixture():
    data = io.BytesIO()
    c = Canvas(data, pagesize=(620, 800))
    c.setFont("Helvetica", 9)
    for basis in ["Consolidated", "Standalone"]:
        c.drawString(40, 770, "Acme Industries Limited INE123A01016")
        c.drawString(40, 746, basis + " Financial Statements")
        c.drawString(40, 725, "INR crore")
        for x in [440, 530]:
            c.drawRightString(x, 705, "Year ended")
        c.drawRightString(440, 685, "March 31, 2026")
        c.drawRightString(530, 685, "March 31, 2025")
        for i, (label, current, prior) in enumerate(
            [
                (
                    "Debt Equity Ratio (number of times)",
                    "0.45" if basis == "Consolidated" else "0.22",
                    "0.6",
                ),
                ("Current ratio (number of times)", "1.5", "1.2"),
                ("Net profit margin (%)", "(5.00)", "10.00"),
                ("Revenue from operations", "1,23,456.78", "100000.00"),
                ("Total borrowings", "45.00", "40.00"),
                ("Shareholders equity", "100.00", "80.00"),
                ("Basic EPS (INR)", "8.23", "7.00"),
            ]
        ):
            y = 660 - i * 30
            c.drawString(40, y, label)
            c.drawRightString(440, y, current)
            c.drawRightString(530, y, prior)
        c.showPage()
        c.setFont("Helvetica", 9)
    c.save()
    raw = data.getvalue()
    reader = PdfReader(io.BytesIO(raw))
    pages = [
        {"pdf_page": i + 1, "text": page.extract_text()} for i, page in enumerate(reader.pages)
    ]
    doc = {
        "id": str(uuid.uuid4()),
        "kind": "annual_report",
        "source_url": "https://issuer.example/report.pdf",
        "discovery_label": "Annual report",
        "fetched_at": "2026-06-01T00:00:00Z",
        "sha256": "verified-hash",
    }
    return (
        raw,
        pages,
        doc,
        {"symbol": "ACME", "isin": "INE123A01016", "name": "Acme Industries Limited"},
    )


def test_native_cells_preserve_geometry_dates_basis_units_and_page_citations():
    raw, pages, doc, company = pdf_fixture()
    facts, _ = extract_metric_cells(
        raw,
        doc,
        pages,
        company,
        {"debt_equity", "current_ratio", "net_margin", "revenue", "eps"},
        [1, 2],
    )
    latest = [f for f in facts if f.period_end == "2026-03-31"]
    de = {f.basis: f for f in latest if f.metric == "debt_equity"}
    assert de["consolidated"].value == Decimal(".45") and de["standalone"].value == Decimal(".22")
    assert (
        de["consolidated"].citation["pdf_page"] == 1 and de["standalone"].citation["pdf_page"] == 2
    )
    assert de["consolidated"].citation["evidence_scope"] == "page"
    assert de["consolidated"].citation["metric_evidence"]["cell_bbox"]
    assert all(f.period_kind == "year" for f in latest)
    revenue = next(f for f in latest if f.metric == "revenue")
    assert (
        revenue.value == Decimal("123456.78")
        and revenue.currency == "INR"
        and revenue.unit == "crore"
    )
    assert next(f for f in latest if f.metric == "net_margin").value == -5
    assert next(f for f in latest if f.metric == "eps").unit == "per_share"


def test_explicit_prose_needs_value_period_and_unit():
    _, _, doc, company = pdf_fixture()
    pages = [
        {
            "pdf_page": 1,
            "text": "Acme Industries Limited INE123A01016\nConsolidated Financial Statements\nThe consolidated debt to equity ratio was 0.45 times as at March 31, 2026.",
        }
    ]
    facts = extract_metric_prose(doc, pages, company, {"debt_equity"})
    assert len(facts) == 1 and facts[0].value == Decimal(".45")
    pages[0]["text"] = pages[0]["text"].replace("0.45 times", "a capital monitoring measure")
    assert not extract_metric_prose(doc, pages, company, {"debt_equity"})


def test_wrong_issuer_and_tata_pre_demerger_are_rejected():
    raw, pages, doc, company = pdf_fixture()
    company["isin"] = "INE999A01016"
    assert not issuer_verified(company, pages)
    assert not extract_metric_cells(raw, doc, pages, company, {"debt_equity"}, [1])[0]
    from finn.metric_evidence import entity_period_allowed

    assert not entity_period_allowed({"symbol": "TMCV"}, "2025-03-31")
    assert entity_period_allowed({"symbol": "TMCV"}, "2026-03-31")
    assert not issuer_verified(
        {"symbol": "TMCV", "isin": "INE1TAE01010", "name": "Tata Motors Limited"},
        [{"pdf_page": 1, "text": "Tata Motors Limited INE155A01022"}],
    )


def test_numerical_route_reuses_persistent_cache_without_pdf_or_models(monkeypatch):
    company = {"symbol": "ACME", "isin": "INE123A01016", "name": "Acme Industries Limited"}
    document = {"id": "doc", "sha256": "hash", "kind": "annual_report", "extraction_version": "v1"}

    class Store:
        def rows(self, table, **filters):
            if table == "finn_search_documents":
                return [document]
            if table == "finn_research_cache" and "cache_key" in filters:
                return [
                    {
                        "result": {
                            "question": "debt/equity",
                            "financial_metrics": {
                                "results": [
                                    {
                                        "id": "debt_equity",
                                        "status": "unavailable",
                                        "reason": "A compatible source value was not established.",
                                    }
                                ]
                            },
                            "cached": False,
                        }
                    }
                ]
            if table == "finn_research_cache":
                return []
            pytest.fail("Unnecessary source read")

        def get_pdf(self, *a):
            pytest.fail("Repeated PDF extraction")

    monkeypatch.setattr(metric_research, "resolve_identity", lambda *a, **k: company)
    result = metric_research.numerical_research(Store(), "ACME", "D/E", cached_only=True)
    assert result["cached"] and result["question"] == "D/E"


def test_quarter_eps_reuses_quarter_column_validation_excluding_ytd():
    data = io.BytesIO()
    c = Canvas(data, pagesize=(650, 800))
    c.setFont("Helvetica", 8)
    c.drawString(35, 770, "Acme Industries Limited INE123A01016")
    c.drawString(35, 750, "Consolidated Financial Results")
    c.drawString(35, 730, "INR million")
    c.drawCentredString(350, 710, "Quarter ended")
    c.drawCentredString(475, 710, "Six months ended")
    c.drawCentredString(550, 710, "Year ended")
    xs = [300, 350, 400, 450, 500, 550]
    for x, date in zip(
        xs, ["30 Sep 26", "30 Jun 26", "30 Sep 25", "30 Sep 26", "30 Sep 25", "31 Mar 26"]
    ):
        c.drawRightString(x, 690, date)
    labels = (
        ["Revenue from operations"]
        + ["Expense item " + str(i) for i in range(9)]
        + ["Profit before tax", "Profit for the period", "Basic EPS"]
    )
    for i, label in enumerate(labels):
        c.drawString(35, 665 - i * 18, label)
        for j, x in enumerate(xs):
            c.drawRightString(x, 665 - i * 18, f"{1000 + i * 100 + j:.2f}")
    c.save()
    raw = data.getvalue()
    _, _, doc, company = pdf_fixture()
    doc["kind"] = "quarterly_results"
    pages = [{"pdf_page": 1, "text": PdfReader(io.BytesIO(raw)).pages[0].extract_text()}]
    facts, _ = extract_metric_cells(raw, doc, pages, company, {"eps"}, [1])
    assert [(f.period_end, f.period_kind) for f in facts] == [
        ("2026-09-30", "quarter"),
        ("2026-06-30", "quarter"),
        ("2025-09-30", "quarter"),
    ]


def test_validated_quarterly_image_cells_use_the_verified_chunk_not_empty_native_page():
    from finn.financial_tables import VERSION
    from finn.financials import RESULTS_VERSION

    _, _, doc, company = pdf_fixture()
    quote = "Revenue from operations | 2026-06-30: 100.00"
    cell = {
        "metric": "Revenue",
        "raw_value": "100.00",
        "value": "100",
        "unit": "crore",
        "currency": "INR",
        "period_end": "2026-06-30",
        "period_kind": "quarter",
        "accounting_basis": "consolidated",
        "image_verification": {"method": "two_image_reads", "pdf_sha256": doc["sha256"]},
    }
    citation = {
        "id": "verified-chunk",
        "document_id": doc["id"],
        "pdf_page": 2,
        "quote": quote,
        "source_url": doc["source_url"],
        "financial_evidence": cell,
    }
    records = [
        {
            "result": {
                "financial_results": {"version": VERSION, "result_version": RESULTS_VERSION},
                "claims": [{"citation": citation}],
            }
        }
    ]
    pages = [
        {"pdf_page": 1, "text": "Acme Industries Limited INE123A01016"},
        {"pdf_page": 2, "text": "Scanned statement page"},
    ]
    chunks = [
        {
            "id": "verified-chunk",
            "document_id": doc["id"],
            "pdf_page": 2,
            "body": "Verified image transcription. " + quote,
        }
    ]
    assert not metric_research.verified_quarterly_facts(records, doc, pages, company)
    facts = metric_research.verified_quarterly_facts(records, doc, pages, company, chunks)
    assert len(facts) == 1 and facts[0].value == 100
    cell["image_verification"]["pdf_sha256"] = "wrong-source"
    assert not metric_research.verified_quarterly_facts(records, doc, pages, company, chunks)
