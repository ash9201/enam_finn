"""Page-aware extraction and conservative table evidence for the feasibility gate."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import io
import re

import pdfplumber
from pydantic import BaseModel, Field
from pypdf import PdfReader


class FinancialFact(BaseModel):
    metric: str
    raw_value: str
    value: Decimal
    period: str | None = None
    period_kind: str | None = None
    currency: str | None = None
    unit: str | None = None
    accounting_basis: str | None = None
    actual_or_guidance: str | None = None
    pdf_page: int = Field(ge=1)
    source_url: str
    evidence: str
    validated: bool = False


def comparison_blockers(left: FinancialFact, right: FinancialFact) -> list[str]:
    """Extraction is not validation. Unknown metadata must not produce a comparison."""
    blockers = []
    for side, fact in [("earlier", left), ("later", right)]:
        if not fact.validated:
            blockers.append(f"{side} figure has not been validated against the source")
        for name in [
            "period",
            "period_kind",
            "currency",
            "unit",
            "accounting_basis",
            "actual_or_guidance",
        ]:
            if getattr(fact, name) in (None, "", "unknown", "mixed"):
                blockers.append(f"{side} {name} is unresolved")
        if not fact.evidence.strip() or not fact.source_url.startswith("https://"):
            blockers.append(f"{side} source evidence is missing")
    for name in ["metric", "period_kind", "currency", "unit", "accounting_basis"]:
        if getattr(left, name) != getattr(right, name):
            blockers.append(f"{name} differs between the figures")
    return blockers


def metadata_candidates(text: str) -> dict:
    text = " ".join(text.split())
    basis = [
        name for name in ["consolidated", "standalone"] if re.search(rf"\b{name}\b", text, re.I)
    ]
    units = re.findall(
        r"(?:₹|`|\bINR\b|\bUSD\b|\bRs\.?|rupees|dollars)[^\n]{0,35}?(?:crore|million|lakh|billion)(?:s)?",
        text,
        re.I,
    )
    periods = re.findall(
        r"\b(?:FY\s?\d{2,4}(?:[-–]\d{2,4})?|(?:March|June|September|December|Mar|Jun|Sep|Dec)\s+\d{1,2},?\s+20\d{2}|20\d{2}[-–]20?\d{2})\b",
        text,
        re.I,
    )
    return {
        "basis_candidate": basis[0] if len(basis) == 1 else "mixed" if basis else None,
        "unit_labels": list(dict.fromkeys(units))[:12],
        "period_labels": list(dict.fromkeys(periods))[:20],
        "validated_for_financial_comparison": False,
    }


def financial_header_settings(page) -> dict | None:
    """Use explicit header anchors when present; never guess numerical column meaning.

    This improves unruled statements while remaining an unvalidated extraction. Notes
    may span cells; all raw words and page text remain available for review.
    """
    words = page.extract_words()
    notes = [
        word for word in words if word["text"].lower() == "note" and word["top"] < page.height * 0.4
    ]
    for note in notes:
        labels = [
            word
            for word in words
            if word["text"].lower() == "particulars" and abs(word["top"] - note["top"]) < 4
        ]
        years = sorted(
            [
                word
                for word in words
                if re.fullmatch(r"20\d{2}", word["text"])
                and note["top"] <= word["top"] < note["top"] + 45
                and word["x0"] > note["x1"]
            ],
            key=lambda word: (word["top"], word["x0"]),
        )
        if labels and len(years) >= 2 and abs(years[0]["top"] - years[1]["top"]) < 4:
            first, second = sorted(years[:2], key=lambda word: word["x0"])
            boundaries = [
                labels[0]["x0"] - 2,
                note["x0"] - 12,
                (note["x1"] + first["x0"]) / 2,
                (first["x1"] + second["x0"]) / 2,
                second["x1"] + 1,
            ]
            if boundaries == sorted(boundaries):
                return {
                    "vertical_strategy": "explicit",
                    "explicit_vertical_lines": boundaries,
                    "horizontal_strategy": "text",
                }
    return None


def extract_document(data: bytes, metadata: dict, *, table_page_limit: int = 8) -> dict:
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("Password-protected PDF is unsupported.")
    if len(reader.pages) > 700:
        raise ValueError("This PDF exceeds the prototype's 700-page processing limit.")
    pages = []
    scored = []
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text(extraction_mode="layout") or ""
        # Plain extraction follows PDF content-stream order, which usually preserves
        # narrative columns. Keep layout text separately for tables and source review.
        reading_text = page.extract_text(extraction_mode="plain") or text
        pages.append(
            {
                "pdf_page": number,
                "text": text,
                "reading_text": reading_text,
                "metadata_candidates": metadata_candidates(text),
            }
        )
        # Prefer numeric financial-statement pages over a contents-page mention.
        headings = len(
            re.findall(
                r"balance sheet|cash flows?|statement of (?:profit|income)|revenue[s]? from operations|consolidated financial statements",
                text,
                re.I,
            )
        )
        digits = len(re.findall(r"\b[\d,]+(?:\.\d+)?\b", text))
        first_lines = " ".join(line.strip() for line in text.splitlines() if line.strip())[:180]
        statement_start = bool(
            re.match(
                r"(?:Consolidated|Standalone)\s+(?:Balance Sheet|Statement of (?:Profit|Income|Cash))",
                first_lines,
                re.I,
            )
        )
        if headings and digits >= 25:
            scored.append((1000 * statement_start + headings * 5 + min(digits, 100) / 20, number))
    if sum(len(page["text"].strip()) for page in pages) < 100:
        raise ValueError(
            "This PDF has no readable text. Image-only documents are not supported by this prototype."
        )
    selected = sorted({number for _, number in sorted(scored, reverse=True)[:table_page_limit]})
    if not selected:
        selected = list(range(1, min(len(pages), 3) + 1))
    tables = []
    extraction_warnings = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for number in selected:
            try:
                page = pdf.pages[number - 1]
                found = page.find_tables()
                method = "ruled_lines"
                if not found:
                    header_settings = financial_header_settings(page)
                    if header_settings:
                        found = page.find_tables(header_settings)
                        method = "financial_header_anchors_candidate"
                    if not found:
                        found = page.find_tables(
                            {
                                "vertical_strategy": "text",
                                "horizontal_strategy": "text",
                                "min_words_vertical": 3,
                            }
                        )
                        method = "text_alignment_candidate"
                for index, table in enumerate(found[:12]):
                    cells = table.extract()
                    if len(cells) < 2 or max((len(row) for row in cells), default=0) < 2:
                        continue
                    tables.append(
                        {
                            "table_id": f"p{number}-t{index + 1}",
                            "pdf_page": number,
                            "bbox": list(table.bbox),
                            "cells": cells,
                            "extraction_method": method,
                            "header_rows_candidate": cells[:3],
                            "page_context": pages[number - 1]["text"][:16000],
                            "metadata_candidates": pages[number - 1]["metadata_candidates"],
                            "quality": "unvalidated_candidate",
                            "approved_for_financial_comparison": False,
                            "source_url": metadata["source_url"],
                        }
                    )
            except Exception as exc:
                extraction_warnings.append({"pdf_page": number, "error_type": type(exc).__name__})
            finally:
                pdf.pages[number - 1].close()
    return {
        **metadata,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "page_numbering": "1-based PDF page, not printed report pagination",
        "page_count": len(pages),
        "pages": pages,
        "tables": tables,
        "table_pages_checked": selected,
        "table_extraction_warnings": extraction_warnings,
        "table_coverage": "Bounded financial-page sample; not a complete table extraction.",
        "financial_comparisons_enabled": False,
    }


def citation_is_supported(quote: str, page_text: str) -> bool:
    normalise = lambda value: " ".join(value.split()).casefold()
    return bool(quote.strip()) and normalise(quote) in normalise(page_text)


def resolve_source_quote(quote: str, source_text: str) -> str | None:
    """Return the original source slice, allowing only PDF whitespace differences.

    Character content is never edited. Figures are subsequently checked against this
    original slice, so e.g. source '1 00' cannot validate a generated figure '100'.
    """
    if not quote.strip():
        return None
    compact, offsets = [], []
    for index, character in enumerate(source_text):
        if not character.isspace():
            for lowered in character.casefold():
                compact.append(lowered)
                offsets.append(index)
    wanted = "".join(quote.split()).casefold()
    position = "".join(compact).find(wanted)
    if position < 0:
        return None
    return source_text[offsets[position] : offsets[position + len(wanted) - 1] + 1]
