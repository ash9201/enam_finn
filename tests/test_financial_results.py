import io
from decimal import Decimal

import pytest
from finn.financial_tables import extract_results_pdf, parse_date, parse_number, shift_quarter
from finn.financials import RowMap, RowSelection, compare, eligible_rows, validate_cells
from reportlab.pdfgen.canvas import Canvas


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1,21,076.24", "121076.24"),
        ("98,989.01", "98989.01"),
        ("(82.30)", "-82.30"),
        ("0", "0"),
        ("12,90175", None),
        ("1,2,345.00", None),
        ("12.345.67", None),
        ("—", None),
        ("1 00", None),
        ("NaN", None),
    ],
)
def test_source_numbers_are_not_repaired(raw, expected):
    assert parse_number(raw) == (Decimal(expected) if expected is not None else None)


def test_quarter_date_and_immediate_periods():
    assert parse_date("30 Sep 26 Unaudited") == "2026-09-30"
    assert parse_date("September 30,2025") == "2025-09-30"
    assert parse_date("30 Sep 26 AND 30 Sep 25") is None
    assert shift_quarter("2026-03-31", -3) == "2025-12-31"
    assert shift_quarter("2024-02-29", -12) == "2023-02-28"


def table_pdf():
    stream = io.BytesIO()
    c = Canvas(stream, pagesize=(730, 800))
    c.setFont("Helvetica", 9)
    c.drawCentredString(
        365,
        770,
        "CONSOLIDATED FINANCIAL RESULTS FOR THE QUARTER AND SIX MONTHS ENDED 30 SEPTEMBER 2026",
    )
    c.drawString(50, 752, "INR million")
    ends = [300, 365, 430, 495, 560, 625]
    c.drawCentredString(350, 730, "Quarter ended")
    c.drawCentredString(513, 730, "Six")
    c.drawCentredString(513, 717, "months ended")
    c.drawCentredString(607, 730, "Year ended")
    for x, label in zip(
        ends, ["30 Sep 26", "30 Jun 26", "30 Sep 25", "30 Sep 26", "30 Sep 25", "31 Mar 26"]
    ):
        c.drawRightString(x, 700, label)
    labels = (
        ["Revenue from operations"]
        + ["Expense item " + str(i) for i in range(9)]
        + ["Profit before tax", "Profit for the period"]
    )
    for index, label in enumerate(labels):
        y = 670 - index * 20
        c.drawString(50, y, label)
        for column, x in enumerate(ends):
            c.drawRightString(x, y, f"{1000 + index * 100 + column:.2f}")
    c.save()
    return stream.getvalue()


def test_merged_and_wrapped_headers_do_not_admit_ytd_or_title_dates():
    result = extract_results_pdf(table_pdf(), {})
    table = result["tables"][0]
    assert (
        table["basis"] == "consolidated"
        and table["currency"] == "INR"
        and table["unit"] == "million"
    )
    assert [(c["index"], c["period_end"]) for c in table["columns"]] == [
        (1, "2026-09-30"),
        (2, "2026-06-30"),
        (3, "2025-09-30"),
    ]


def fact(value="100", **changes):
    return {
        "validated": True,
        "metric": "Revenue",
        "value": value,
        "period_end": "2026-09-30",
        "period_kind": "quarter",
        "currency": "INR",
        "unit": "million",
        "accounting_basis": "consolidated",
        "definition": "revenue_from_operations",
        "document_id": "same",
        **changes,
    }


def test_decimal_changes_and_unit_normalisation():
    result = compare(
        fact("98989.01"), fact("82097.32", period_end="2026-06-30"), "2026-06-30", "million"
    )
    assert result == {"absolute": "16891.69", "percent": "20.58", "reason": None}
    assert (
        compare(
            fact("10"), fact("80", unit="lakh", period_end="2026-06-30"), "2026-06-30", "million"
        )["absolute"]
        == "2.00"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"accounting_basis": "standalone"},
        {"currency": "USD"},
        {"definition": "total_income"},
        {"period_kind": "six_months"},
        {"period_end": "2026-03-31"},
        {"document_id": "other", "comparability_note": True},
    ],
)
def test_incompatible_figures_do_not_get_compared(change):
    result = compare(
        fact(), fact("80", **{"period_end": "2026-06-30", **change}), "2026-06-30", "million"
    )
    assert result["absolute"] is None and result["percent"] is None and result["reason"]


@pytest.mark.parametrize("base", ["0", "-10"])
def test_nonpositive_bases_keep_absolute_change_but_withhold_percent(base):
    result = compare(fact("10"), fact(base, period_end="2026-06-30"), "2026-06-30", "million")
    assert Decimal(result["absolute"]) == Decimal(10) - Decimal(base)
    assert result["percent"] is None and result["reason"]


def test_unvalidated_figures_do_not_get_compared():
    result = compare(
        fact(), fact("90", period_end="2026-06-30", validated=False), "2026-06-30", "million"
    )
    assert result["absolute"] is None and result["reason"]


def test_uniquely_identified_rows_do_not_need_an_llm():
    from finn.financials import map_rows

    class NoModel:
        def rpc(self, *args):
            pytest.fail("Unambiguous source rows must not consume model quota")

    table = extract_results_pdf(table_pdf(), {})["tables"][0]
    mapping, usage = map_rows(NoModel(), [table])
    assert {s.metric for s in mapping.selections} == {"Revenue", "PBT", "PAT"}
    assert usage["method"] == "deterministic_unique_rows"


def test_mapping_cannot_substitute_total_income_or_shareholder_pat():
    table = extract_results_pdf(table_pdf(), {})["tables"][0]
    row = eligible_rows(table, "Revenue")[0]
    row["cells"][0] = "Total income"
    accepted, rejected = validate_cells(
        [table],
        RowMap(
            selections=[
                RowSelection(table_id=table["table_id"], metric="Revenue", row_index=row["index"])
            ]
        ),
    )
    assert not accepted and rejected


def test_damaged_decimal_cell_is_withheld_without_losing_valid_quarters():
    table = extract_results_pdf(table_pdf(), {})["tables"][0]
    row = eligible_rows(table, "PBT")[0]
    row["cells"][2] = "12,90175"
    accepted, rejected = validate_cells(
        [table],
        RowMap(
            selections=[
                RowSelection(table_id=table["table_id"], metric="PBT", row_index=row["index"])
            ]
        ),
    )
    assert len(accepted) == 2 and {f["period_end"] for f in accepted} == {
        "2026-09-30",
        "2025-09-30",
    }
    assert rejected and all(f["value"] != "12901.75" for f in accepted)
