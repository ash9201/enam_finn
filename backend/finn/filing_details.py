"""Bounded, cached extraction of official filing narratives, never financial tables."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from pypdf import PdfReader

from finn.config import load_local_env
from finn.corpus import now
from finn.sources import fetch_pdf, public_client, validate_source_url
from finn.store import open_store

VERSION = "official-filing-narrative-v1"
DISPLAY_VERSION = "filing-display-v3"
MAX_PAGES = 8


def compact(text):
    return re.sub(r"\s+", " ", text).strip()


def feed_text(row):
    return compact(row["description"].split("|SUBJECT:")[0])


def input_hash(row):
    return hashlib.sha256(
        json.dumps([row["source_url"], row["description"], row["title"]]).encode()
    ).hexdigest()


def clean_display(text):
    text = re.sub(r"\(?\bDIN\s*[:\-]?\s*\d{8}\)?", "", text, flags=re.I)
    text = re.sub(
        r"^.{0,180}?(?:has informed the Exchange(?: that| about| regarding)?|has submitted to the Exchange[, ]*)\s*",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"^In continuation of.{0,350}?inter alia\s*:?\s*", "", text, flags=re.I)
    text = re.sub(r"^\d+\.\s*", "", text)
    text = re.sub(r";\s*and\s*\d+\.\s*", "; and ", text)
    text = compact(text)
    return text[:1].upper() + text[1:]


def concise(text):
    text = re.sub(r"\s+([,.;])", r"\1", clean_display(text))
    for match in re.finditer(r"[.!?]\s+(?=[A-Z])", text):
        prefix = text[: match.start() + 1]
        if match.start() > 65 and not re.search(r"\b(?:Prof|Mr|Ms|Dr|Rs|[A-Za-z])\.$", prefix):
            return prefix
    if len(text) > 450:
        return text[:450].rsplit(" ", 1)[0] + "…"
    return text if text.endswith((".", "!", "?", "\u2026")) else text.rsplit(" ", 1)[0] + "\u2026"


def table_like(text):
    return bool(
        re.search(r"ISIN", text, re.I)
        and re.search(r"date of allotment|actual date of payment|due date", text, re.I)
    )


def format_details(row, detail):
    """Presentation-only update from cached, already extracted evidence."""
    result = {**detail, "display_version": DISPLAY_VERSION}
    body, raw = feed_text(row), row["title"].lower()
    if result.get("summary"):
        result["summary"] = concise(result["summary"])
    result["evidence"] = [
        e
        for e in result.get("evidence", [])
        if not table_like(e["quote"])
        and not (
            re.match(r"fixed\b", e["quote"], re.I)
            and not re.search(r"record date", e["quote"], re.I)
        )
    ]
    official = [e for e in result["evidence"] if e["kind"] == "official_document"]
    if re.search(
        r"audio recording|video recording|link of recording|transcript|investor presentation",
        row["description"],
        re.I,
    ):
        result.update(
            category="earnings_call",
            priority=1,
            event_kind="earnings_call",
            event_key=None,
            actual_results=False,
        )
        result["headline"] = (
            "Investor presentation available"
            if "presentation" in body.lower()
            else "Earnings-call transcript available"
            if "transcript" in body.lower()
            else "Earnings-call recording available"
        )
        weak = clean_display(body).strip(" .").lower() in {
            "audio recording/video recording",
            "link of recording",
            "investor presentation",
        }
        if weak:
            passage = next(
                (
                    e["quote"]
                    for e in official
                    if re.search(r"recording|transcript|presentation", e["quote"], re.I)
                ),
                None,
            )
            result["summary"] = concise(passage) if passage else None
    if result.get("category") == "results":
        narrative = next(
            (
                e["quote"]
                for e in official
                if re.search(r"approved.{0,150}financial results", e["quote"], re.I)
            ),
            None,
        )
        if narrative:
            result["summary"] = concise(narrative)
        if re.search(r"passed an enabling resolution|authoris\w* the issuance", body, re.I):
            result["summary"] = concise(body)
            result["headline"] = "Financial results & debt-issue authorisation"
        elif re.search(r"copy of (?:a )?media release|press release", body, re.I):
            result["headline"] = "Financial-results media release"
            result["actual_results"] = False
    if "security cover" in raw:
        result["headline"] = "Debt security cover certificate"
    elif "utilization of issue" in raw or "utilisation of issue" in raw:
        result["headline"] = "Use of debt-issue proceeds"
    elif "regulation 52" in raw:
        result["headline"] = "Debt-related financial disclosures"
    if re.search(r"security cover|regulation 52|utili[sz]ation of issue", raw) and result.get(
        "event_key"
    ):
        result["summary"] = "Supporting debt disclosure within the filed financial-results package."
    if "board meeting" in raw and result.get("category") == "corporate_action":
        result["headline"] = (
            "Dividend-related board outcome"
            if "dividend" in body.lower()
            else "Corporate-action board outcome"
        )
    if result.get("summary") and table_like(result["summary"]):
        result["summary"] = None
    if "redemption" in raw:
        result["headline"] = "Debt redemption or payment disclosure"
    if not result.get("summary"):
        result["status"] = "headline_only"
    return result


def source_date(text):
    text = compact(text).replace("Sept ", "Sep ")
    text = re.sub(r"(\d)(?:st|nd|rd|th)\b", r"\1", text)
    for pattern in [
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%Y-%m-%d",
    ]:
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            pass
    return None


DATE = r"(?:\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{2}[./]\d{2}[./]\d{4}|\d{4}-\d{2}-\d{2})"


def reporting_period(text):
    match = re.search(
        r"(?:quarter|half[ -]year|six months|year).{0,35}?ended\s*[:\-]?\s*(" + DATE + ")",
        text,
        re.I,
    )
    return source_date(match[1]) if match else None


def narrative_excerpts(pages):
    """Keep exact contiguous native-text spans; avoid numeric statement pages."""
    patterns = [
        r"(?:approved|adopted|submitted).{0,140}financial results.{0,240}",
        r"(?:Prof\.|Mr\.|Ms\.|Dr\.).{0,100}(?:complet\w*|resign\w*|appoint\w*).{0,300}",
        r"(?:declared|recommended).{0,100}dividend.{0,220}",
        r"(?:fixed.{0,70}record date|record date).{0,200}",
        r"(?:commercial operation|commission\w*|awarded|capacity expansion).{0,250}",
        r"(?:audio|video|recording|transcript).{0,230}",
        r"(?:acquisition|penalty|resignation|appointment|downgrade).{0,250}",
    ]
    excerpts = []
    for page in pages:
        text = compact(page["text"])
        # A dense table is not a validated sentence, amount or comparison.
        if len(re.findall(r"\d", text)) / max(1, len(text)) > 0.16 or table_like(text):
            continue
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if not match:
                continue
            quote = match[0].strip()
            if len(quote) < 35 or any(quote in e["quote"] for e in excerpts):
                continue
            excerpts.append(
                {"quote": quote, "pdf_page": page.get("pdf_page"), "field": page.get("field")}
            )
            if len(excerpts) >= 4:
                return excerpts
    return excerpts


def present(row, *, pages=(), source=None, limitation=None):
    from finn.briefing import classify_filing

    feed = feed_text(row)
    extracted = narrative_excerpts(pages)
    context_pages = pages[:64] if source and source.get("method") == "exchange_xml" else pages[:2]
    body = compact(" ".join([feed, *[p["text"] for p in context_pages]]))
    category, priority, _ = classify_filing(feed)
    if category == "unclassified" and pages:
        category, priority, _ = classify_filing(body)
    # A specialised disclosure keeps its identity even within a results package.
    if category == "management_change" and "independent" in body.lower():
        refined, value, _ = classify_filing(body)
        if refined == "management_change":
            priority = value
    period = reporting_period(body)
    scheduled = category == "management_change" and priority == 1
    actual_results = bool(
        re.search(
            r"(?:approved|adopted|submitted).{0,170}(?:financial results|the financial results)",
            body,
            re.I,
        )
    )
    result_support = bool(
        re.search(
            r"security cover|regulation 52|utili[sz]ation of issue proceeds", row["title"], re.I
        )
    )
    financial_family = (
        category in ["results", "meeting_notice", "publication"]
        or result_support
        or (category == "corporate_action" and actual_results)
    )
    event_kind = (
        "results" if financial_family and period else "scheduled_tenure" if scheduled else category
    )
    title = {
        "results": "Financial results filed",
        "meeting_notice": "Board meeting scheduled",
        "publication": "Results publication notice",
        "management_change": "Leadership disclosure",
        "scheduled_tenure": "Independent director completes scheduled term",
        "business_update": "Business development",
        "corporate_action": "Corporate action",
        "earnings_call": "Earnings-call material",
        "capital": "Funding or debt disclosure",
        "routine": "Routine disclosure",
        "unclassified": "Announcement awaiting classification",
        "m_and_a": "Acquisition or restructuring disclosure",
        "litigation": "Legal or regulatory disclosure",
        "investor_meeting": "Investor meeting notice",
        "credit_rating": "Credit-rating update",
    }.get("scheduled_tenure" if scheduled else category, row["title"])
    raw = row["title"].casefold()
    if "record date" in raw:
        title = "Dividend record date" if "dividend" in body.lower() else "Record date announced"
    elif "dividend" in raw:
        title = "Dividend declared" if "declared" in body.lower() else "Dividend disclosure"
    elif result_support:
        title = "Debt-security supporting disclosure"
    elif re.search(r"recording|audio|video", body, re.I) and category == "earnings_call":
        title = "Earnings-call recording available"
    elif re.search(r"commercial operation", feed, re.I):
        title = "Commercial operation declared"
    elif "snapshot" in feed.lower():
        title = "Quarterly operational and financial snapshot"
    if category == "results" and period:
        title = "Financial results for " + datetime.fromisoformat(period).strftime("%d %b %Y")

    # Substantive exchange text is a primary source too; never present it as a PDF quote.
    cleaned = clean_display(feed)
    generic = (
        not cleaned
        or cleaned.casefold().strip(" .") == row["title"].casefold().strip(" .")
        or bool(
            re.fullmatch(
                r"(?:Change in Directors/KMP/SMP/Auditor/RTA|General Updates|Financial Results Updates|.*about Change in Directors/KMP/SMP/Auditor/RTA)",
                cleaned,
                re.I,
            )
        )
    )
    summary = (
        cleaned if not generic else clean_display(extracted[0]["quote"]) if extracted else None
    )
    if not generic:
        evidence = [
            {"quote": feed, "pdf_page": None, "field": None, "kind": "exchange_feed"},
            *[{**e, "kind": "official_document"} for e in extracted],
        ]
    else:
        evidence = [{**e, "kind": "official_document"} for e in extracted]
    entity = re.search(r"\bDIN\s*[:\-]?\s*(\d{8})", body, re.I)
    effective = re.search(
        r"(?:Company on|effective (?:from|on)|cessation.{0,15})\s*(" + DATE + ")", body, re.I
    )
    effective_date = source_date(effective[1]) if effective else None
    # Multi-person disclosures are not forced into a single-director event.
    single_person = len(set(re.findall(r"\bDIN\s*[:\-]?\s*(\d{8})", body, re.I))) == 1
    event_key = None
    if financial_family and period:
        event_key = "results:" + period
    elif scheduled and entity and effective_date and single_person:
        event_key = f"tenure:{entity[1]}:{effective_date}"
    return {
        "version": VERSION,
        "input_hash": input_hash(row),
        "checked_at": now(),
        "status": "source_extracted"
        if extracted
        else "feed_details"
        if summary
        else "headline_only",
        "headline": title,
        "summary": summary[:750] if summary else None,
        "category": category,
        "priority": priority,
        "event_kind": event_kind,
        "event_key": event_key,
        "period_end": period,
        "actual_results": actual_results,
        "interpretation": "The filing describes completion of a scheduled term, rather than an unexpected resignation."
        if scheduled
        else None,
        "evidence": evidence[:5],
        "source": source,
        "limitation": limitation,
    }


def official_pages(client, url, content_cache=None):
    parsed = urlparse(url)
    if parsed.hostname not in {
        "nsearchives.nseindia.com",
        "www.bseindia.com",
        "archives.nseindia.com",
    }:
        raise ValueError("Only linked official exchange documents are extracted.")
    if parsed.path.lower().endswith(".xml"):
        validate_source_url(url)
        with client.stream("GET", url, follow_redirects=False) as response:
            response.raise_for_status()
            data = bytearray()
            for part in response.iter_bytes():
                data.extend(part)
                if len(data) > 2 * 1024 * 1024:
                    raise ValueError("Structured disclosure exceeds the extraction limit.")
        if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
            raise ValueError("External or declared XML entities are not supported.")
        root = ET.fromstring(data)
        pages = []
        for element in root.iter():
            field = element.tag.rsplit("}", 1)[-1]
            value = compact(" ".join(element.itertext())) if not len(element) else ""
            if value and re.search(
                r"Remarks|Details|TextBlock|Reason|NameOfDesignatedPerson|DesignationOfDesignatedPerson|EffectiveDate",
                field,
            ):
                pages.append({"field": field, "text": value[:8000]})
        return (
            bytes(data),
            pages,
            {"url": url, "method": "exchange_xml", "pages_scanned": None, "total_pages": None},
        )
    data, final = fetch_pdf(client, url, max_bytes=30 * 1024 * 1024)
    digest = hashlib.sha256(data).hexdigest()
    if content_cache is not None and digest in content_cache:
        old_data, old_pages, old_meta = content_cache[digest]
        return old_data, old_pages, {**old_meta, "url": final}
    reader = PdfReader(io.BytesIO(data))
    pages = [
        {"pdf_page": i + 1, "text": reader.pages[i].extract_text() or ""}
        for i in range(min(MAX_PAGES, len(reader.pages)))
    ]
    result = (
        data,
        pages,
        {
            "url": final,
            "method": "native_pdf_text",
            "pages_scanned": len(pages),
            "total_pages": len(reader.pages),
        },
    )
    if content_cache is not None:
        content_cache[digest] = result
    return result


def needs_extraction(row):
    old = row.get("enrichment") or {}
    if old.get("version") != VERSION or old.get("input_hash") != input_hash(row):
        return True
    if old.get("limitation"):
        try:
            return datetime.fromisoformat(old["checked_at"]) < datetime.now(
                timezone.utc
            ) - timedelta(hours=6)
        except (ValueError, KeyError):
            return True
    return False


def enrich_filings(store, *, limit=6, symbol=None, retry_unavailable=False):
    filters = {"order": "published_at.desc", "limit": 1000}
    if symbol:
        filters["symbol"] = "eq." + symbol
    rows = store.rows("finn_filings", **filters)
    refreshed = 0
    for row in rows:
        saved = row.get("enrichment") or {}
        if saved.get("version") == VERSION and saved.get("input_hash") == input_hash(row):
            detail = format_details(row, saved)
            if (
                detail != saved
                or row["category"] != detail["category"]
                or row["priority"] != detail["priority"]
            ):
                store.patch(
                    "finn_filings",
                    {
                        "enrichment": detail,
                        "category": detail["category"],
                        "priority": detail["priority"],
                    },
                    id="eq." + row["id"],
                )
                row.update(
                    enrichment=detail, category=detail["category"], priority=detail["priority"]
                )
                refreshed += 1
    pending = [
        row
        for row in rows
        if needs_extraction(row)
        or retry_unavailable
        and (row.get("enrichment") or {}).get("limitation")
    ]
    # Material/uncertain items before routine work; time breaks priority ties.
    pending.sort(key=lambda row: -row["priority"])
    updated, unavailable, downloads = 0, 0, 0
    download_cache, content_cache, stored_hashes = {}, {}, set()
    with public_client() as client:
        for row in pending[: max(0, min(limit, 100))]:
            source, pages, limitation = None, [], None
            if row["priority"] > 0:
                try:
                    if row["source_url"] not in download_cache:
                        download_cache[row["source_url"]] = official_pages(
                            client, row["source_url"], content_cache
                        )
                        downloads += 1
                    data, pages, source = download_cache[row["source_url"]]
                    source = {
                        **source,
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "fetched_at": now(),
                    }
                    if (
                        source["method"] == "native_pdf_text"
                        and source["sha256"] not in stored_hashes
                    ):
                        store.put_pdf(f"filings/{row['symbol']}/{source['sha256']}.pdf", data)
                        stored_hashes.add(source["sha256"])
                    if not any(len(compact(p["text"])) > 50 for p in pages):
                        limitation = "No usable native text was extracted; no OCR or inferred details were substituted."
                except Exception:
                    unavailable += 1
                    limitation = "Official document details could not be extracted. Available exchange text is shown; the original link remains accessible."
            result = format_details(
                row, present(row, pages=pages, source=source, limitation=limitation)
            )
            store.patch(
                "finn_filings",
                {
                    "enrichment": result,
                    "category": result["category"],
                    "priority": result["priority"],
                },
                id="eq." + row["id"],
            )
            updated += 1
    return {
        "updated": updated,
        "unavailable": unavailable,
        "downloads": downloads,
        "presentation_refreshed": refreshed,
        "pending": max(0, len(pending) - updated),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--symbol")
    parser.add_argument("--retry-unavailable", action="store_true")
    args = parser.parse_args()
    load_local_env()
    with open_store() as store:
        print(
            json.dumps(
                enrich_filings(
                    store,
                    limit=args.limit,
                    symbol=args.symbol,
                    retry_unavailable=args.retry_unavailable,
                )
            )
        )


if __name__ == "__main__":
    main()
