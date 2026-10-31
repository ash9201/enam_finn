"""Geometry-preserving quarterly statements. Candidates never establish financial facts."""

import hashlib
import io
import re
from calendar import monthrange
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from itertools import pairwise

import pdfplumber

VERSION = "quarterly-tables-v3"
METRICS = ["Revenue", "EBITDA", "PBT", "PAT"]


def parse_number(raw):
    """Reject damaged grouping/decimal text; never repair an OCR figure."""
    text = raw.strip().replace("\u2212", "-")
    if re.fullmatch(r"\(.*\)", text):
        text = "-" + text[1:-1]
    if not re.fullmatch(r"-?(?:\d+|\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3})(?:\.\d+)?", text):
        return None
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None


def parse_date(text):
    months = {
        m: i
        for i, m in enumerate(
            ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1
        )
    }
    clean = re.sub(r"[^a-z0-9]", " ", text.lower())
    patterns = [
        r"\b(\d{1,2})\s+([a-z]{3,9})\s+(\d{4}|\d{2})\b",
        r"\b([a-z]{3,9})\s+(\d{1,2})\s+(\d{4}|\d{2})\b",
        r"\b(\d{1,2})\s+(\d{1,2})\s+(20\d{2})\b",
    ]
    found = set()
    for index, pattern in enumerate(patterns):
        for a, b, year in re.findall(pattern, clean):
            day, month = (
                (int(a), months.get(b[:3]))
                if index == 0
                else (int(b), months.get(a[:3]))
                if index == 1
                else (int(a), int(b))
            )
            year = int(year) + (2000 if len(year) == 2 else 0)
            try:
                value = date(year, month, day)
                if (
                    value.day == monthrange(year, month)[1]
                    and 1990 <= year
                    and value <= date.today()
                ):
                    found.add(value.isoformat())
            except (ValueError, TypeError):
                pass
    return next(iter(found)) if len(found) == 1 else None


def shift_quarter(period, months):
    d = date.fromisoformat(period)
    year, month0 = divmod(d.year * 12 + d.month - 1 + months, 12)
    return date(year, month0 + 1, monthrange(year, month0 + 1)[1]).isoformat()


def grouped_lines(words):
    lines = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        row = next((row for row in reversed(lines[-3:]) if abs(row["y"] - word["top"]) < 2.5), None)
        if row is None:
            row = {"y": word["top"], "words": []}
            lines.append(row)
        row["words"].append(word)
    return [sorted(row["words"], key=lambda w: w["x0"]) for row in lines]


def metric_allowed(metric, label):
    label = re.sub(r"\s+", " ", label.lower())
    if metric == "Revenue":
        return bool(re.search(r"(?:revenue|income) from operations", label))
    if metric == "EBITDA":
        return bool(
            re.search(r"\bebitda\b|earnings before interest.*(?:depreciation|amortisation)", label)
        )
    if metric == "PBT":
        return bool(re.search(r"profit.*before\s*tax", label)) and not re.search(
            r"exceptional|extraordinary|cash flow", label
        )
    return bool(
        re.search(r"(?:net\s+)?profit.*(?:after\s*tax|for (?:the )?(?:period|quarter|year))", label)
    ) and not re.search(r"comprehensive|attributable|before|margin", label)


def candidate_table(words, page_number):
    lines = grouped_lines(words)
    numeric = [w for row in lines for w in row if re.fullmatch(r"\(?-?[\d,]+\.\d{2}\)?", w["text"])]
    clusters = []
    for w in sorted(numeric, key=lambda w: w["x1"]):
        if not clusters or abs(clusters[-1]["x"] - w["x1"]) > 3:
            clusters.append({"x": w["x1"], "count": 1})
        else:
            clusters[-1]["count"] += 1
    centres = sorted(c["x"] for c in clusters if c["count"] >= 6)
    if not 3 <= len(centres) <= 9:
        return None
    gap = min(b - a for a, b in pairwise(centres))
    boundaries = [centres[0] - gap + 3] + [x + 3 for x in centres]
    rows = []
    for row in lines:
        cells = ["" for _ in range(len(centres) + 1)]
        for w in row:
            x = (w["x0"] + w["x1"]) / 2
            column = next(
                (i + 1 for i in range(len(centres)) if boundaries[i] <= x < boundaries[i + 1]), 0
            )
            cells[column] = (cells[column] + " " + w["text"]).strip()
        rows.append(
            {
                "index": len(rows),
                "cells": cells,
                "text": " ".join(w["text"] for w in row),
                "y": row[0]["top"],
            }
        )
    first = next(
        (
            r["index"]
            for r in rows
            if metric_allowed("Revenue", r["cells"][0])
            and any(parse_number(c) is not None for c in r["cells"][1:])
        ),
        None,
    )
    if first is None:
        # Banks/insurers do not have industrial revenue/EBITDA semantics.
        first = next(
            (
                r["index"]
                for r in rows
                if re.search(
                    r"interest (?:earned|income)|premium.*earned", r["text"], re.IGNORECASE
                )
            ),
            None,
        )
    if first is None:
        return None
    header = "\n".join(r["text"] for r in rows[:first])
    basis_hits = re.findall(r"\b(consolidated|standalone)\b", header, re.IGNORECASE)
    basis = (
        next(iter({b.lower() for b in basis_hits}))
        if len({b.lower() for b in basis_hits}) == 1
        else None
    )
    scale_hits = re.findall(r"\b(lakhs?|crores?|millions?|billions?)\b", header, re.IGNORECASE)
    scales = {x.lower().rstrip("s") for x in scale_hits}
    currencies = {
        code
        for code, pattern in [
            ("INR", r"\u20b9|\b(?:rs|inr|rupees)\b"),
            ("USD", r"\$|\b(?:usd|dollars)\b"),
            ("EUR", r"\u20ac|\beur\b"),
        ]
        if re.search(pattern, header, re.IGNORECASE)
    }
    currency = next(iter(currencies)) if len(currencies) == 1 else None
    unit = next(iter(scales)) if len(scales) == 1 else None
    # Scope labels may span three quarter columns. Use their original geometry,
    # including repeated 'quarter ended' headings and merged half/year headings.
    scopes = []
    scope_rows = []
    for row_index, line in enumerate(lines[:first]):
        for i, w in enumerate(line):
            group = line[i : i + 4]
            text = " ".join(v["text"] for v in group).lower()
            match = re.match(
                r"(quarter\s*ended|three months\s*ended|(?:half[- ]?year|six(?: months)?|nine(?: months)?|twelve(?: months)?)(?:\s*ended)?|year\s*ended)",
                text,
            )
            if match:
                count = len(match.group(0).split())
                chosen = group[:count]
                scopes.append(
                    (
                        (chosen[0]["x0"] + chosen[-1]["x1"]) / 2,
                        "quarter" if text.startswith(("quarter", "three")) else "other",
                        row_index,
                    )
                )
                if text.startswith(("quarter", "three")):
                    scope_rows.append(row_index)
    scopes = [scope for scope in scopes if scope[2] >= max(scope_rows, default=0)]
    columns = []
    for i in range(1, len(centres) + 1):
        text = " ".join(r["cells"][i] for r in rows[max(scope_rows, default=0) : first])
        period = parse_date(text)
        x = (boundaries[i - 1] + boundaries[i]) / 2
        kind = min(scopes, key=lambda scope: abs(scope[0] - x))[1] if scopes else "unknown"
        if period and kind == "quarter":
            columns.append({"index": i, "period_end": period, "header": text})
    if not columns:
        return None
    return {
        "table_id": f"p{page_number}",
        "pdf_page": page_number,
        "basis": basis,
        "currency": currency,
        "unit": unit,
        "header": header,
        "columns": columns,
        "rows": rows,
        "sector_note": "Financial-sector revenue/EBITDA may be inapplicable."
        if re.search(
            r"interest (?:earned|income)|premium.*earned",
            header + " ".join(r["cells"][0] for r in rows),
            re.IGNORECASE,
        )
        else None,
    }


def extract_results_pdf(data, metadata, *, progress=lambda stage: None):
    pages, tables = [], []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        if len(pdf.pages) > 60:
            raise ValueError("Quarterly filing exceeds the bounded 60-page extraction limit.")
        for number, page in enumerate(pdf.pages, 1):
            words = page.extract_words(x_tolerance=1.8, y_tolerance=2)
            lines = grouped_lines(words)
            text = "\n".join(" ".join(w["text"] for w in row) for row in lines)
            table = candidate_table(words, number)
            if table:
                tables.append(table)
            pages.append(
                {
                    "pdf_page": number,
                    "text": text,
                    "reading_text": text,
                    "metadata_candidates": {"financial_figures_validated": False},
                }
            )
            progress(f"pages:{number}/{len(pdf.pages)}")
            page.close()
    if not any(len(p["text"]) > 100 for p in pages):
        raise ValueError(
            "Scanned/unreadable filing: no reliable native figures; OCR is not enabled."
        )
    return {
        **metadata,
        "pages": pages,
        "tables": tables,
        "page_count": len(pages),
        "sha256": hashlib.sha256(data).hexdigest(),
        "extracted_at": datetime.now(UTC).isoformat(),
        "table_coverage": "Geometry-aligned native quarterly statements; each mapped cell separately validated.",
        "table_pages_checked": [t["pdf_page"] for t in tables],
        "table_extraction_warnings": [],
        "text_extractor": VERSION,
    }
