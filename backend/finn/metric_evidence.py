"""Bounded native-PDF metric cells. Similarity and LLM numbers are not evidence."""

import hashlib
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID, uuid5

import pdfplumber

from finn.documents import resolve_source_quote
from finn.financial_tables import candidate_table, grouped_lines, parse_date, parse_number
from finn.financials import company_identity
from finn.metric_registry import REGISTRY, metric_matches, normalise

VERSION = "metric-cells-v1.1"


def number_word(text):
    return parse_number(text[:-1] if text.endswith(("%", "×", "x", "X")) else text)


def compatible_unit(metric, unit):
    kind = REGISTRY[metric].unit_kind
    if kind == "money":
        return unit in SCALES
    if kind in {"times", "percent"}:
        return unit in {"times", "%"}
    if kind == "per_share":
        return unit in {"per_share", "per_user", "per_room"}
    return unit == "days" if kind == "days" else True


SCALES = {
    "rupee": Decimal(1),
    "lakh": Decimal(100000),
    "crore": Decimal(10000000),
    "million": Decimal(1000000),
    "billion": Decimal(1000000000),
}
RESTRUCTURED = {
    "TMCV": ("INE1TAE01010", "tmlcommercialvehicleslimited", "2025-10-01"),
    "TMPV": ("INE155A01022", "tatamotorslimited", "2025-10-01"),
}


@dataclass
class Fact:
    metric: str
    value: Decimal
    unit: str
    currency: str | None
    period_end: str
    period_kind: str
    basis: str
    entity: str
    citation: dict
    definition: str
    raw_value: str = ""
    method: str = "reported"
    inputs: list = field(default_factory=list)
    formula: str | None = None


def issuer_verified(company, pages):
    cover = " ".join(p["text"] for p in pages if p["pdf_page"] <= 5)
    isins = set(re.findall(r"\bINE[A-Z0-9]{9}\b", cover.upper()))
    if isins and company["isin"] not in isins:
        return False
    clean = company_identity(cover)
    if company["symbol"] in RESTRUCTURED:
        isin, former, _ = RESTRUCTURED[company["symbol"]]
        return company["isin"] == isin and (isin in isins or company_identity(former) in clean)
    return company["isin"] in isins or company_identity(company["name"]) in clean


def entity_period_allowed(company, period):
    # Older combined Tata entity figures are not current TMCV/TMPV figures.
    return company["symbol"] not in RESTRUCTURED or period >= RESTRUCTURED[company["symbol"]][2]


def body_lines(text):
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not ("CONSOLIDATED" in line.upper() and "STANDALONE" in line.upper())
    ]


def basis_contexts(pages):
    current, source, result = None, None, {}
    for p in sorted(pages, key=lambda p: p["pdf_page"]):
        for line in body_lines(p["text"]):
            match = re.match(
                r"^(?:notes (?:forming part of|to) )?(consolidated|standalone)\s+(?:financial(?:\s+(?:statements|results|performance))?|balance sheet|statement|cash flow)\b",
                line,
                re.I,
            )
            if match:
                current, source = match[1].lower(), p["pdf_page"]
        result[p["pdf_page"]] = (current, source)
    return result


def page_citation(document, page, quote, provenance):
    canonical = " ".join(page["text"].split())
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    quote = resolve_source_quote(quote, canonical) or canonical
    return {
        "id": str(uuid5(UUID(document["id"]), f"page-evidence:{page['pdf_page']}:{digest}")),
        "document_id": document["id"],
        "pdf_page": page["pdf_page"],
        "quote": quote,
        "source_url": document["source_url"],
        "document_url": document.get("final_url") or document["source_url"],
        "kind": document["kind"],
        "document_label": document["discovery_label"],
        "published_at": document.get("published_at"),
        "reporting_period": document.get("reporting_period"),
        "fetched_at": document["fetched_at"],
        "evidence_scope": "page",
        "page_hash": digest,
        "metric_evidence": provenance,
    }


def row_metric(label, preceding):
    if re.search(r"discontinued|pro.forma|combined.company|before.demerger", label, re.I):
        return None
    if (
        re.search(
            r"adjusted|underlying|normalised|normalized|excluding.exceptional|before.exceptional",
            label,
            re.I,
        )
        and "ebitda" not in label.lower()
    ):
        return None
    if re.fullmatch(r"\s*(?:[ab][.)]\s*)?(?:basic|diluted)\s*", label, re.I) and re.search(
        r"earnings per (?:equity )?share", preceding[-800:], re.I
    ):
        return "diluted_eps" if "diluted" in label.lower() else "eps"
    clean = re.sub(r"\[[^\]]*\]", "", label)
    clean = re.sub(r"^\s*(?:[a-z]|[ivx]+|\d+)[.)]\s*", "", clean, flags=re.I)
    clean = re.sub(r"\([^)]*\)", "", clean)
    keys = metric_matches(clean)
    if len(keys) != 1:
        return None
    key = keys[0]
    alias = next(
        (
            a
            for a in sorted(REGISTRY[key].aliases, key=len, reverse=True)
            if normalise(clean).startswith(normalise(a))
        ),
        None,
    )
    if not alias:
        return None  # Mentions inside a paragraph or a formula are not row labels.
    tail = normalise(clean)[len(normalise(alias)) :].strip()
    if tail and not re.fullmatch(
        r"(?:ratio|net|%|times|inr|rs|crore|crores|million|lakh|lakhs|basic|diluted|[ivx]+)(?:\s+(?:ratio|times|%|crores?|lakhs?|million))*",
        tail,
    ):
        return None
    if key == "ebitda" and re.search(
        r"adjusted|underlying|excluding.exceptional|before.exceptional", label, re.I
    ):
        return "adjusted_ebitda"
    if key == "pe" and re.search(r"forward|expected|estimated", label, re.I):
        return "forward_pe"
    if key == "debt" and normalise(clean) == "borrowings":
        sections = re.findall(
            r"\b(non[- ]current liabilities|current liabilities)\b", preceding, re.I
        )
        return (
            ("long_debt" if "non" in sections[-1].lower() else "short_debt") if sections else None
        )
    return key


def date_headers(lines):
    headers = []
    for i, line in enumerate(lines):
        if not re.search(
            r"\b(?:20\d{2}|\d{2}[-/.]\d{2}[-/.]\d{2})\b", " ".join(w["text"] for w in line)
        ):
            continue
        for start in range(len(line)):
            for size in range(1, 5):
                group = line[start : start + size]
                text = " ".join(w["text"] for w in group)
                if len(group) != size or not re.search(r"\d", text):
                    continue
                period = parse_date(text)
                if not period:
                    continue
                x = group[-1]["x1"]
                local = " ".join(
                    w["text"]
                    for row in lines[max(0, i - 3) : i + 1]
                    for w in row
                    if abs(w["x1"] - x) < 70
                )
                if not re.search(r"year|quarter|month|as at|as on|from", local, re.I):
                    continue
                own = " ".join(
                    w["text"]
                    for row in lines[max(0, i - 3) : i + 1]
                    for w in row
                    if group[0]["x0"] - 12 <= (w["x0"] + w["x1"]) / 2 <= x + 8
                )
                kind = (
                    "stub"
                    if re.search(
                        r"\bfrom\b|half.year|(?:six|nine|eighteen|fifteen|6|9|15|18|24)\s+months",
                        own,
                        re.I,
                    )
                    else "quarter"
                    if re.search(r"quarter|(?:three|3)\s+months", local, re.I)
                    else "year"
                    if re.search(r"year|(?:twelve|12)\s+months", local, re.I)
                    else "point"
                )
                # Shortest actual date span, then nearest row, disambiguates columns.
                if not any(
                    h["period"] == period and abs(h["x"] - x) < 3 and h["y"] == line[0]["top"]
                    for h in headers
                ):
                    headers.append(
                        {
                            "x": x,
                            "y": line[0]["top"],
                            "period": period,
                            "kind": kind,
                            "text": text,
                            "context": local,
                        }
                    )
    return headers


def source_unit(metric, label, context):
    kind = REGISTRY[metric].unit_kind
    if re.search(r"\(\s*%\s*\)|\bpercent(?:age)?\b", label, re.I) or "%" in label:
        return "%", None
    if re.search(r"\btimes\b|number of times|\bx\b|×", label, re.I):
        return "times", None
    if re.search(r"\bdays\b", label, re.I):
        return "days", None
    if kind in {"percent", "times"}:
        # A ratio column requires a stated unit; do not assume 0.31 means 31%.
        return None, None
    currency = {
        code
        for code, pat in [
            ("INR", r"₹|\b(?:INR|Rs\.?|rupees)\b"),
            ("USD", r"\bUSD\b|US\$"),
            ("EUR", r"\bEUR\b|€"),
        ]
        if re.search(pat, context, re.I)
    }
    scales = set(
        x.lower().rstrip("s")
        for x in re.findall(r"\b(lakhs?|crores?|millions?|billions?)\b", context, re.I)
    )
    if len(currency) != 1:
        return None, None
    if kind == "per_share":
        return (
            "per_user" if metric == "arpu" else "per_room" if metric == "arr" else "per_share"
        ), next(iter(currency))
    return (next(iter(scales)), next(iter(currency))) if len(scales) == 1 else (None, None)


def extract_metric_cells(data, document, pages, company, wanted, selected, *, max_pages=18):
    if not issuer_verified(company, pages):
        return [], [
            "Issuer identity could not be verified from this document's cover/ISIN; figures were not used."
        ]
    bases = basis_contexts(pages)
    by_page = {p["pdf_page"]: p for p in pages}
    facts, warnings = [], []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for number in list(dict.fromkeys(selected))[:max_pages]:
            if number not in by_page or not 1 <= number <= len(pdf.pages):
                continue
            page = pdf.pages[number - 1]
            words = page.extract_words(x_tolerance=1.8, y_tolerance=2)
            quarter_table = (
                candidate_table(words, number) if document["kind"] == "quarterly_results" else None
            )
            lines = grouped_lines(words)
            # Remove the repeated report-navigation strip, which names both bases.
            lines = [
                ln
                for ln in lines
                if not (
                    any(w["text"].upper() == "CONSOLIDATED" for w in ln)
                    and any(w["text"].upper() == "STANDALONE" for w in ln)
                )
            ]
            headers = date_headers(lines)
            basis, basis_page = bases.get(number, (None, None))
            local_bases = {
                m.lower()
                for ln in lines[:10]
                for m in re.findall(
                    r"\b(consolidated|standalone)\b", " ".join(w["text"] for w in ln), re.I
                )
            }
            if len(local_bases) == 1:
                basis, basis_page = next(iter(local_bases)), number
            if not basis:
                page.close()
                continue
            for index, line in enumerate(lines):
                values = [
                    (w, number_word(w["text"]))
                    for w in line
                    if w["x0"] > page.width * 0.35 and number_word(w["text"]) is not None
                ]
                if not values:
                    continue
                label = " ".join(w["text"] for w in line if w["x1"] <= values[0][0]["x0"])
                preceding = "\n".join(
                    " ".join(w["text"] for w in ln) for ln in lines[max(0, index - 20) : index]
                )
                key = row_metric(label, preceding)
                if key not in wanted:
                    continue
                # Header/row units, never arbitrary numbers in narrative text.
                header_context = "\n".join(
                    " ".join(w["text"] for w in ln) for ln in lines[max(0, index - 22) : index]
                )
                unit, currency = source_unit(key, label, header_context)
                declared_unit = unit
                if (
                    not unit
                    and values
                    and all(w["text"].endswith(("%", "×", "x", "X")) for w, _ in values)
                ):
                    unit = "%" if values[0][0]["text"].endswith("%") else "times"
                if not unit:
                    continue
                for word, value in values:
                    quarter_column = None
                    if quarter_table:
                        bounds = quarter_table["column_bounds"]
                        middle = (word["x0"] + word["x1"]) / 2
                        column = next(
                            (
                                i
                                for i in range(1, len(bounds))
                                if bounds[i - 1] <= middle < bounds[i]
                            ),
                            None,
                        )
                        quarter_column = next(
                            (c for c in quarter_table["columns"] if c["index"] == column), None
                        )
                        if quarter_column is None:
                            continue
                    eligible = [
                        h
                        for h in headers
                        if 2 < word["top"] - h["y"] < 430 and abs(word["x1"] - h["x"]) < 26
                    ]
                    eligible.sort(key=lambda h: (-h["y"], abs(word["x1"] - h["x"])))
                    if not eligible and not quarter_column:
                        continue
                    h = (
                        {
                            "period": quarter_column["period_end"],
                            "kind": "quarter",
                            "text": quarter_column["header"],
                            "x": word["x1"],
                            "y": word["top"] - 1,
                        }
                        if quarter_column
                        else eligible[0]
                    )
                    tied = [
                        e for e in eligible if abs(e["y"] - h["y"]) < 3 and abs(e["x"] - h["x"]) < 3
                    ]
                    if (
                        not quarter_column and len({e["period"] for e in tied}) != 1
                    ) or not entity_period_allowed(company, h["period"]):
                        continue
                    suffix_unit = (
                        "%"
                        if word["text"].endswith("%")
                        else "times"
                        if word["text"].endswith(("x", "X", "×"))
                        else None
                    )
                    if declared_unit and suffix_unit and suffix_unit != declared_unit:
                        continue
                    actual_unit = suffix_unit or unit
                    if not compatible_unit(key, actual_unit):
                        continue
                    provenance = {
                        "metric": key,
                        "raw_value": word["text"],
                        "row_label": label,
                        "column_header": h["text"],
                        "period_kind": h["kind"],
                        "accounting_basis": basis,
                        "basis_source_page": basis_page,
                        "unit": actual_unit,
                        "currency": currency,
                        "cell_bbox": [word[k] for k in ["x0", "top", "x1", "bottom"]],
                        "verification": "native_pdf_geometry",
                        "document_sha256": document["sha256"],
                    }
                    quote = " ".join(w["text"] for w in line)
                    citation = page_citation(document, by_page[number], quote, provenance)
                    definition = (
                        "owners_equity"
                        if key == "equity" and re.search(r"shareholder|owners", label, re.I)
                        else key
                    )
                    facts.append(
                        Fact(
                            key,
                            value,
                            actual_unit,
                            currency,
                            h["period"],
                            h["kind"],
                            basis,
                            company["isin"],
                            citation,
                            definition,
                            word["text"],
                        )
                    )
            page.close()
    return facts, warnings


def extract_metric_prose(document, pages, company, wanted, selected=None):
    """Only explicit values with a date, stated unit and unambiguous metric label."""
    if not issuer_verified(company, pages):
        return []
    contexts = basis_contexts(pages)
    facts = []
    for page in pages:
        if selected is not None and page["pdf_page"] not in selected:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", " ".join(page["text"].split())):
            period = parse_date(sentence)
            if not period or not entity_period_allowed(company, period):
                continue
            basis_hits = {
                b.lower() for b in re.findall(r"\b(consolidated|standalone)\b", sentence, re.I)
            }
            basis = (
                next(iter(basis_hits)).lower()
                if len(basis_hits) == 1
                else contexts[page["pdf_page"]][0]
                if not basis_hits
                else None
            )
            if not basis:
                continue
            for key in set(metric_matches(sentence)) & wanted:
                for alias in sorted(REGISTRY[key].aliases, key=len, reverse=True):
                    pattern = re.escape(alias).replace(r"\ ", r"[- /]*")
                    m = re.search(
                        r"\b"
                        + pattern
                        + r"\s+(?:was|is|of|stood at|at|amounted to)\s*(?:(?:INR|Rs\.?|USD|₹)\s*)?(\(?-?[\d,]+(?:\.\d+)?\)?)\s*(%|times|[x×]|crores?|lakhs?|millions?|billions?)(?=\s|[.,;)]|$)",
                        sentence,
                        re.I,
                    )
                    if not m:
                        continue
                    value = parse_number(m[1])
                    unit, currency = source_unit(key, alias + " " + m[2], sentence)
                    if value is None or not unit or not compatible_unit(key, unit):
                        continue
                    provenance = {
                        "metric": key,
                        "raw_value": m[1],
                        "unit": unit,
                        "currency": currency,
                        "accounting_basis": basis,
                        "verification": "explicit_dated_prose",
                        "document_sha256": document["sha256"],
                    }
                    facts.append(
                        Fact(
                            key,
                            value,
                            unit,
                            currency,
                            period,
                            "year"
                            if re.search(r"year ended", sentence, re.I)
                            else "quarter"
                            if re.search(r"quarter ended", sentence, re.I)
                            else "point",
                            basis,
                            company["isin"],
                            page_citation(document, page, sentence, provenance),
                            key,
                            m[1],
                        )
                    )
                    break
    return facts
