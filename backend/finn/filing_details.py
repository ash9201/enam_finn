"""Bounded, cached extraction of official filing narratives, never financial tables."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse

import httpx
from pypdf import PdfReader

from finn.config import load_local_env
from finn.corpus import now
from finn.sources import fetch_pdf, public_client, validate_source_url
from finn.store import open_store

VERSION = "official-filing-narrative-v1"
DISPLAY_VERSION = "filing-display-v5"
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
    """Clean source wording without dropping words, sentences or imposing display limits."""
    return re.sub(r"\s+([,.;])", r"\1", clean_display(text))


def complete_passage(text):
    """A bounded extraction may end mid-sentence; never promote that tail to a claim."""
    text = concise(text)
    end = 0
    for match in re.finditer(r"[.!?](?=\s|$)", text):
        prefix = text[: match.end()]
        if not re.search(r"\b(?:Prof|Mr|Ms|Dr|Rs|Ltd|Inc|[A-Za-z])\.$|\bw\.e\.f\.$", prefix, re.I):
            end = match.end()
            break
    return text[:end] if end else None


def table_like(text):
    return bool(
        re.search(r"ISIN", text, re.I)
        and re.search(r"date of allotment|actual date of payment|due date", text, re.I)
    )


def format_details(row, detail):
    """Presentation-only update from cached, already extracted evidence."""
    result = {**detail, "display_version": DISPLAY_VERSION}
    body, raw = feed_text(row), row["title"].lower()
    cleaned_feed = clean_display(body)
    informative_feed = (
        bool(cleaned_feed)
        and cleaned_feed.casefold().strip(" .") != raw.strip(" .")
        and not re.fullmatch(
            r"Change in Directors/KMP/SMP/Auditor/RTA|General Updates|Financial Results Updates|Audio Recording/Video Recording|Link of Recording|Investor Presentation",
            cleaned_feed,
            re.I,
        )
    )
    if informative_feed:
        # Recover previously clipped summaries from their preserved primary source.
        result["summary"] = concise(body)
    elif result.get("summary") and re.search(r"(?:\.{3}|\u2026)$", result["summary"]):
        # A legacy clipped native excerpt has no safe missing tail to reconstruct.
        old_prefix = result["summary"].rstrip(".\u2026 ").lower()
        saved = next(
            (
                e["quote"]
                for e in result.get("evidence", [])
                if e["kind"] == "official_document"
                and clean_display(e["quote"]).lower().startswith(old_prefix)
            ),
            None,
        )
        result["summary"] = complete_passage(saved) if saved else None
    if result.get("summary"):
        result["summary"] = concise(result["summary"])
        if result.get("event_kind") == "scheduled_tenure":
            result["summary"] = re.sub(
                r",?\s+and consequently (?:he|she|they).{0,150}end of business hours of said date\.",
                ", effective at the close of business.",
                result["summary"],
                flags=re.I,
            )
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
            event_key=(result.get("recording_reference") or {}).get("event_key"),
            actual_results=False,
        )
        result["headline"] = (
            "Investor presentation available"
            if "presentation" in body.lower()
            else "Earnings-call transcript available"
            if "transcript" in body.lower()
            else "Earnings-call recording available"
        )
        reference = result.get("recording_reference")
        if reference:
            day = datetime.fromisoformat(reference["call_date"]).strftime("%d %b %Y")
            result["headline"] = "Earnings-call recording · " + day
            result["summary"] = (
                f"An {reference['kind']} recording is available for the earnings call held on {day}."
            )
            if result.get("period_end"):
                period = datetime.fromisoformat(result["period_end"]).strftime("%d %b %Y")
                result["summary"] = (
                    result["summary"][:-1] + f", covering results for the period ended {period}."
                )
        weak = clean_display(body).strip(" .").lower() in {
            "audio recording/video recording",
            "link of recording",
            "investor presentation",
        }
        if weak and not reference:
            passage = next(
                (
                    e["quote"]
                    for e in official
                    if re.search(r"recording|transcript|presentation", e["quote"], re.I)
                ),
                None,
            )
            result["summary"] = complete_passage(passage) if passage else None
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
            result["summary"] = complete_passage(narrative)
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
    topic = (
        "security_cover"
        if "security cover" in raw
        else "issue_proceeds"
        if re.search(r"utili[sz]ation of issue", raw)
        else "debt_disclosures"
        if "regulation 52" in raw
        else None
    )
    if topic:
        result.update(event_kind=topic, actual_results=False, category="capital")
        # A shared attachment/quarter does not make these the same investor development.
        digest = (result.get("source") or {}).get("sha256")
        result["event_key"] = f"{topic}:{digest}" if digest else None
        purpose = {
            "security_cover": "A security-cover certificate",
            "issue_proceeds": "A statement on utilisation of issue proceeds",
            "debt_disclosures": "Debt-related financial disclosures",
        }[topic]
        result["summary"] = purpose + (
            " were filed." if topic == "debt_disclosures" else " was filed."
        )
    if result.get("category") == "corporate_action" and str(
        result.get("event_key") or ""
    ).startswith("results:"):
        result.update(event_kind="corporate_action", event_key=None, actual_results=False)
    if result.get("dividend_reference") and result.get("category") == "corporate_action":
        result.update(
            event_kind="dividend",
            event_key=result["dividend_reference"]["event_key"],
            actual_results=False,
        )
        result["headline"] = (
            "Interim dividend & record date"
            if result["dividend_reference"]["type"] == "interim"
            else "Dividend & record date"
        )
        if (result.get("source") or {}).get("method") == "exchange_xml" and str(
            result.get("limitation") or ""
        ).startswith("No usable native text"):
            result["limitation"] = None
    if (
        "board meeting" in raw
        and result.get("category") == "corporate_action"
        and not result.get("dividend_reference")
    ):
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
    result["summary_incomplete"] = bool(
        result.get("summary") and re.search(r"(?:\.{3}|\u2026)$", result["summary"])
    )
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
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%Y-%m-%d",
    ]:
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            pass
    return None


DATE = r"(?:\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}-[A-Za-z]+-\d{4}|\d{2}[./]\d{2}[./]\d{4}|\d{4}-\d{2}-\d{2})"


def reporting_period(text):
    match = re.search(
        r"(?:quarter|half[ -]year|six months|year).{0,35}?ended\s*[:\-]?\s*(" + DATE + ")",
        text,
        re.I,
    )
    return source_date(match[1]) if match else None


def dividend_reference(pages):
    """Use an explicit dividend type and record date, not a shared results period."""
    dates, kinds, evidence = set(), set(), []
    fields = {p.get("field"): p["text"] for p in pages if p.get("field")}
    if fields:
        approved = (
            fields.get(
                "WhetherDeclarationOfInterimDividendOrRecommendationOfFinalDividendApprovedByTheBoard",
                "",
            ).lower()
            == "yes"
        )
        if not approved:
            return None, []
        for page in pages:
            field = page.get("field", "")
            if re.fullmatch(r"RecordDateOf(?:Interim|Final)Dividend", field):
                dates.add(source_date(page["text"]))
            elif field == "FirstTypeOfDividend":
                kinds.add(page["text"].lower())
            else:
                continue
            evidence.append(
                {
                    "quote": page["text"],
                    "field": field,
                    "pdf_page": None,
                    "kind": "official_document",
                }
            )
    else:
        for page in pages:
            text = compact(page["text"])
            types = list(re.finditer(r"\b(interim|final|special)\s+dividend\b", text, re.I))
            records = list(
                re.finditer(
                    r"fixed\s+(" + DATE + r")\s+as\s+(?:the\s+)?[\"“]?record date", text, re.I
                )
            )
            if not types or not records:
                continue
            kinds.update(match[1].lower() for match in types)
            dates.update(source_date(match[1]) for match in records)
            evidence.extend(
                {
                    "quote": match[0],
                    "field": None,
                    "pdf_page": page.get("pdf_page"),
                    "kind": "official_document",
                }
                for match in [types[0], *records]
            )
    if (
        len(dates) != 1
        or None in dates
        or len(kinds) != 1
        or not kinds.issubset({"interim", "final", "special"})
    ):
        return None, []
    day, kind = dates.pop(), kinds.pop()
    return {"record_date": day, "type": kind, "event_key": f"dividend:{kind}:{day}"}, evidence


def recording_reference(pages):
    """Require both an explicit call date and recording link, never a filing date/title."""
    fields = {}
    for page in pages:
        field = page.get("field")
        if field:
            if field in fields and fields[field] != page["text"]:
                return None, []
            fields[field] = page["text"]
    date_fields = [
        (key, value)
        for key, value in fields.items()
        if re.fullmatch(r"DateOfCallFor(?:Audio|Video)Recording", key)
    ]
    if date_fields:
        dates = {source_date(value) for _, value in date_fields}
        links = [
            (key, value)
            for key, value in fields.items()
            if re.fullmatch(r"WeblinkOf(?:Audio|Video)Recording", key)
        ]
        if len(dates) != 1 or None in dates or len(links) != 1:
            return None, []
        day, link = dates.pop(), links[0][1]
        kind = "video" if "Video" in links[0][0] else "audio"
        evidence = [
            {"quote": value, "field": key, "pdf_page": None, "kind": "official_document"}
            for key, value in [*date_fields, links[0]]
        ]
    else:
        matches = []
        for page in pages:
            text = compact(page["text"])
            calls = list(
                re.finditer(
                    r"(?:conference call|analyst meet).{0,30}?(?:held on|on)\s*(" + DATE + ")",
                    text,
                    re.I,
                )
            )
            if len({source_date(call[1]) for call in calls}) > 1:
                return None, []
            call = calls[0] if calls else None
            recording = re.search(
                r"(?:audio|video) recording.{0,500}?(https?://[^\s<>]+)", text, re.I
            )
            if call and recording and source_date(call[1]):
                matches.append((page, call, recording))
        if len(matches) != 1:
            return None, []
        page, call, recording = matches[0]
        day, link = source_date(call[1]), recording[1].rstrip(".,;")
        kind = "video" if recording[0].lower().startswith("video") else "audio"
        evidence = [
            {
                "quote": match[0],
                "field": None,
                "pdf_page": page.get("pdf_page"),
                "kind": "official_document",
            }
            for match in [call, recording]
        ]
    parsed = urlparse(link)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        return None, []
    # www variants are the same company URL; retain path/query/anchor distinctions.
    canonical = urlunparse(
        (
            "https",
            parsed.netloc.lower().removeprefix("www."),
            parsed.path.rstrip("/"),
            "",
            parsed.query,
            parsed.fragment,
        )
    )
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:20]
    return {
        "call_date": day,
        "url": link,
        "kind": kind,
        "event_key": f"recording:{kind}:{day}:{digest}",
    }, evidence


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
        cleaned if not generic else complete_passage(extracted[0]["quote"]) if extracted else None
    )
    if not generic:
        evidence = [
            {"quote": feed, "pdf_page": None, "field": None, "kind": "exchange_feed"},
            *[{**e, "kind": "official_document"} for e in extracted],
        ]
    else:
        evidence = [{**e, "kind": "official_document"} for e in extracted]
    topic_pattern = (
        r"Security Cover Certificate[^.]+\."
        if "security cover" in raw
        else r"Statement of Utili[sz]ation of Issue Proceeds.*?for the quarter ended\s*" + DATE
        if re.search(r"utili[sz]ation of issue", raw)
        else r"disclosures under Regulation 52.*?for the quarter ended\s*" + DATE
        if "regulation 52" in raw
        else None
    )
    if topic_pattern:
        evidence = []
        for page in context_pages:
            match = re.search(topic_pattern, compact(page["text"]), re.I)
            if match:
                evidence.append(
                    {
                        "quote": match[0],
                        "pdf_page": page.get("pdf_page"),
                        "field": page.get("field"),
                        "kind": "official_document",
                    }
                )
                break
        if not evidence:
            evidence = [{"quote": feed, "pdf_page": None, "field": None, "kind": "exchange_feed"}]
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
    additional = []
    if scheduled and single_person:
        for page in context_pages:
            text = compact(page["text"])
            roles = re.search(
                r"Accordingly,? (?:he|she|they) (?:has|have) also ceased.{0,650}?effective from said date\.",
                text,
                re.I,
            )
            if roles:
                additional.append(clean_display(roles[0]))
                evidence.append(
                    {
                        "quote": roles[0],
                        "pdf_page": page.get("pdf_page"),
                        "field": page.get("field"),
                        "kind": "official_document",
                    }
                )
    reference, reference_evidence = (None, [])
    if re.search(
        r"audio recording|video recording|link of recording", body, re.I
    ) and not re.search(r"transcript|investor presentation", feed, re.I):
        reference, reference_evidence = recording_reference(context_pages)
        evidence = [*reference_evidence, *evidence]
    dividend, dividend_evidence = (
        dividend_reference(context_pages) if category == "corporate_action" else (None, [])
    )
    evidence = [*dividend_evidence, *evidence]
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
        "summary": summary,
        "category": category,
        "priority": priority,
        "event_kind": event_kind,
        "event_key": event_key,
        "period_end": period,
        "effective_date": effective_date if scheduled and single_person else None,
        "additional_details": list(dict.fromkeys(additional)),
        "recording_reference": reference,
        "dividend_reference": dividend,
        "topic_version": 1,
        "event_evidence_version": 1,
        "actual_results": actual_results,
        "interpretation": "The filing describes completion of a scheduled term, rather than an unexpected resignation."
        if scheduled
        else None,
        "evidence": evidence[:5],
        "source": source,
        "limitation": limitation,
    }


def official_pages(client, url, content_cache=None):
    try:
        return _official_pages(client, url, content_cache)
    except httpx.ConnectError:
        if urlparse(url).hostname != "nsearchives.nseindia.com":
            raise
        # The exchange's alternate archive host; keep the original filing URL on the row.
        return _official_pages(
            client,
            url.replace("https://nsearchives.nseindia.com/", "https://archives.nseindia.com/", 1),
            content_cache,
        )


def _official_pages(client, url, content_cache=None):
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
                r"Remarks|Details|TextBlock|Reason|NameOfDesignatedPerson|DesignationOfDesignatedPerson|EffectiveDate|DateOfCallFor(?:Audio|Video)Recording|WeblinkOf(?:Audio|Video)Recording|Dividend",
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


def enrich_filings(
    store,
    *,
    limit=6,
    symbol=None,
    retry_unavailable=False,
    refresh_event_evidence=False,
    refresh_topics=False,
):
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
        if not (refresh_event_evidence or refresh_topics)
        and (
            needs_extraction(row)
            or retry_unavailable
            and (row.get("enrichment") or {}).get("limitation")
        )
        or refresh_topics
        and not (row.get("enrichment") or {}).get("topic_version")
        and row["category"] in {"results", "capital", "corporate_action"}
        or refresh_event_evidence
        and not (row.get("enrichment") or {}).get("event_evidence_version")
        and (
            (row.get("enrichment") or {}).get("event_kind") == "scheduled_tenure"
            or "recording" in (row.get("enrichment") or {}).get("headline", "").lower()
        )
    ]
    # Material/uncertain items before routine work; time breaks priority ties.
    pending.sort(key=lambda row: -row["priority"])
    updated, unavailable, downloads, reused = 0, 0, 0, 0
    download_cache, content_cache, stored_hashes = {}, {}, set()
    with public_client() as client:
        for row in pending[: max(0, min(limit, 100))]:
            source, pages, limitation = None, [], None
            if row["priority"] > 0:
                try:
                    previous = (row.get("enrichment") or {}).get("source") or {}
                    cached = (
                        refresh_topics
                        and previous.get("method") == "native_pdf_text"
                        and previous.get("sha256")
                    )
                    if cached:
                        digest = previous["sha256"]
                        if digest not in content_cache:
                            data = store.get_pdf(f"filings/{row['symbol']}/{digest}.pdf", digest)
                            reader = PdfReader(io.BytesIO(data))
                            pages = [
                                {"pdf_page": i + 1, "text": reader.pages[i].extract_text() or ""}
                                for i in range(min(MAX_PAGES, len(reader.pages)))
                            ]
                            content_cache[digest] = (data, pages, previous)
                        data, pages, _ = content_cache[digest]
                        source = previous  # Extraction time changes; original fetch time does not.
                        reused += 1
                    elif row["source_url"] not in download_cache:
                        download_cache[row["source_url"]] = official_pages(
                            client, row["source_url"], content_cache
                        )
                        downloads += 1
                    if not cached:
                        data, pages, source = download_cache[row["source_url"]]
                        source = {
                            **source,
                            "sha256": hashlib.sha256(data).hexdigest(),
                            "fetched_at": now(),
                        }
                    if (
                        not cached
                        and source["method"] == "native_pdf_text"
                        and source["sha256"] not in stored_hashes
                    ):
                        store.put_pdf(f"filings/{row['symbol']}/{source['sha256']}.pdf", data)
                        stored_hashes.add(source["sha256"])
                    usable = (
                        bool(pages)
                        if source["method"] == "exchange_xml"
                        else any(len(compact(p["text"])) > 50 for p in pages)
                    )
                    if not usable:
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
        "reused_documents": reused,
        "presentation_refreshed": refreshed,
        "pending": max(0, len(pending) - updated),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--symbol")
    parser.add_argument("--retry-unavailable", action="store_true")
    parser.add_argument(
        "--refresh-topics",
        action="store_true",
        help="Reprocess cached results/dividend/debt evidence without re-downloading saved PDFs.",
    )
    parser.add_argument(
        "--refresh-event-evidence",
        action="store_true",
        help="Bounded refresh of cached recording/tenure source references only.",
    )
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
                    refresh_event_evidence=args.refresh_event_evidence,
                    refresh_topics=args.refresh_topics,
                )
            )
        )


if __name__ == "__main__":
    main()
