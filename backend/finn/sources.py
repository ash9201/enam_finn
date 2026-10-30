"""Small, generic live-source probes. No seed-company shortcuts or cached fallbacks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import csv
import io
import ipaddress
import re
import socket
import time
from threading import Lock
from urllib.parse import parse_qs, quote, urljoin, urlparse
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import httpx

USER_AGENT = "Mozilla/5.0 (compatible; FINN/0.1; public financial document research)"
IST = timezone(timedelta(hours=5, minutes=30))
_directory_cache: tuple[float, list[dict]] = (0, [])
_directory_lock = Lock()


def public_client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=45, follow_redirects=True)


def company_directory(client: httpx.Client) -> list[dict]:
    global _directory_cache
    with _directory_lock:
        if _directory_cache[1] and time.monotonic() - _directory_cache[0] < 900:
            return _directory_cache[1]
        response = client.get("https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv")
        response.raise_for_status()
        rows = []
        for original in csv.DictReader(io.StringIO(response.text.lstrip("\ufeff"))):
            row = {key.strip(): value.strip() for key, value in original.items() if key}
            if row.get("SYMBOL"):
                rows.append(
                    {
                        "symbol": row["SYMBOL"],
                        "name": row["NAME OF COMPANY"],
                        "isin": row.get("ISIN NUMBER"),
                        "directory_url": str(response.url),
                    }
                )
        if not rows:
            raise ValueError("The live NSE directory was empty; no company was invented.")
        _directory_cache = (time.monotonic(), rows)
        return rows


def resolve_company(client: httpx.Client, symbol: str) -> dict:
    symbol = symbol.upper().removesuffix(".NS")
    if not re.fullmatch(r"[A-Z0-9&-]{1,30}", symbol):
        raise ValueError("Supply a valid NSE symbol, not a company URL.")
    for row in company_directory(client):
        if row["symbol"] == symbol:
            return row
    raise ValueError(f"NSE symbol {symbol} was not found in the live company directory.")


def discover_documents(client: httpx.Client, company: dict) -> dict:
    """Read link sections only; do not ingest Screener commentary or financial tables."""
    symbol = quote(company["symbol"], safe="")
    response = client.get(f"https://www.screener.in/company/{symbol}/consolidated/")
    if response.status_code == 404:
        response = client.get(f"https://www.screener.in/company/{symbol}/")
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    documents: dict[str, list] = {"annual_report": [], "transcript": []}
    for heading in soup.find_all(["h2", "h3"]):
        title = heading.get_text(" ", strip=True).lower()
        kind = (
            "annual_report"
            if title == "annual reports"
            else "transcript"
            if title == "concalls"
            else None
        )
        if kind is None:
            continue
        listing = heading.find_next("ul", class_="list-links")
        if listing is None:
            continue
        for item in listing.find_all("li", recursive=False):
            for link in item.find_all("a", href=True):
                label = link.get_text(" ", strip=True)
                if kind == "annual_report" and not label.startswith("Annual Report"):
                    continue
                if kind == "transcript" and label != "Transcript":
                    continue
                url = urljoin(str(response.url), link["href"])
                host = (urlparse(url).hostname or "").lower()
                if host.endswith("screener.in"):
                    continue
                context = item.get_text(" ", strip=True)
                period = re.search(r"(?:Annual Report\s+\d{4}|[A-Z][a-z]{2}\s+\d{4})", context)
                documents[kind].append(
                    {
                        "kind": kind,
                        "source_url": url,
                        "discovery_url": str(response.url),
                        "discovery_label": period.group(0) if period else label,
                        "published_at": None,
                        "reporting_period": None,
                        "metadata_note": "Discovery label is not a verified reporting period or publication date.",
                    }
                )
    if not all(documents.values()):
        raise ValueError(
            "The company index does not expose both an annual report and a raw transcript; no summary was substituted."
        )
    return {"company": company, "discovery_url": str(response.url), "documents": documents}


def fetch_pdf(
    client: httpx.Client, url: str, max_bytes: int = 50 * 1024 * 1024
) -> tuple[bytes, str]:
    """Fetch the linked primary document, handling BSE's public HTML PDF wrapper."""
    attempts = [url]
    response = None
    for _ in range(6):
        target = attempts[-1]
        parsed = urlparse(target)
        validate_source_url(target)
        with client.stream("GET", target, follow_redirects=False) as streamed:
            if streamed.is_redirect:
                candidate = urljoin(target, streamed.headers.get("location", ""))
                if candidate in attempts:
                    raise ValueError("Primary source redirects in a loop.")
                attempts.append(candidate)
                continue
            streamed.raise_for_status()
            buffer = bytearray()
            for piece in streamed.iter_bytes():
                buffer.extend(piece)
                if len(buffer) > max_bytes:
                    raise ValueError("Document exceeds the 50 MB feasibility download limit.")
            data, final_url = bytes(buffer), str(streamed.url)
            response = httpx.Response(
                streamed.status_code,
                headers=streamed.headers,
                content=data,
                request=streamed.request,
            )
        if data.lstrip().startswith(b"%PDF-"):
            return data, final_url
        soup = BeautifulSoup(response.text, "html.parser")
        nested = next(
            (
                node.get("src") or node.get("data")
                for node in soup.find_all(["iframe", "embed", "object"])
                if node.get("src") or node.get("data")
            ),
            None,
        )
        if nested:
            candidate = urljoin(final_url, nested)
        elif parsed.hostname.endswith("bseindia.com") and "Pname" in parse_qs(parsed.query):
            # Public attachment path referenced by the exchange's own AnnPdfOpen wrapper.
            name = parse_qs(parsed.query)["Pname"][0]
            if not re.fullmatch(r"[A-Za-z0-9-]+\.pdf", name):
                raise ValueError("Unexpected BSE attachment filename.")
            candidate = f"https://www.bseindia.com/xml-data/corpfiling/AttachHis/{name}"
        else:
            raise ValueError(
                "The source returned HTML instead of a PDF; no alternative content was substituted."
            )
        if candidate in attempts:
            raise ValueError("Document wrapper redirects in a loop.")
        attempts.append(candidate)
    raise ValueError("Could not obtain a primary PDF from the document wrapper.")


def validate_source_url(url: str) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in [None, 443]
    ):
        raise ValueError("Primary documents require a public HTTPS URL without credentials.")
    addresses = {
        item[4][0] for item in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    }
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("Primary source URLs cannot point to local or private network addresses.")


def announcement_probe(client: httpx.Client, company: dict) -> dict:
    feed = announcement_feed(client)
    normalise = lambda text: re.sub(r"[^a-z0-9]", "", text.lower())
    wanted = normalise(company["name"])
    matching = [item for item in feed["items"] if normalise(item["company"]) == wanted]
    return {
        "source_url": feed["source_url"],
        "feed_items": len(feed["items"]),
        "company_items": matching,
        "coverage": "Recent RSS window only; not a complete historical filing archive.",
    }


def announcement_feed(client: httpx.Client) -> dict:
    response = client.get("https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml")
    response.raise_for_status()
    if b"<!DOCTYPE" in response.content.upper() or b"<!ENTITY" in response.content.upper():
        raise ValueError("Unexpected XML declarations in announcement feed.")
    warnings = []
    try:
        items = ET.fromstring(response.content).findall(".//item")
    except ET.ParseError:
        # NSE can serve the feed while it is being rewritten. Retry once, then use
        # only complete, independently valid item elements and disclose partial coverage.
        time.sleep(1)
        response = client.get(
            "https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml",
            headers={"Cache-Control": "no-cache"},
        )
        response.raise_for_status()
        try:
            items = ET.fromstring(response.content).findall(".//item")
        except ET.ParseError:
            if b"<!DOCTYPE" in response.content.upper() or b"<!ENTITY" in response.content.upper():
                raise ValueError("Unexpected XML declarations in announcement feed.")
            items = []
            for match in re.finditer(rb"<item\b[^>]*>.*?</item>", response.content, re.S):
                try:
                    items.append(ET.fromstring(match.group(0)))
                except ET.ParseError:
                    continue
            if not items:
                raise ValueError(
                    "The exchange RSS document was incomplete and had no usable entries."
                )
            warnings.append(
                "Exchange RSS was incomplete; only complete valid entries were processed."
            )
    parsed_items, errors = [], []
    for item in items:
        raw_date = item.findtext("pubDate") or ""
        try:
            published = parse_announcement_date(raw_date)
        except ValueError:
            errors.append({"company": item.findtext("title") or "", "raw_date": raw_date})
            continue
        parsed_items.append(
            {
                "company": item.findtext("title") or "",
                "description": item.findtext("description") or "",
                "source_url": item.findtext("link") or "",
                "published_at": published,
            }
        )
    return {
        "source_url": str(response.url),
        "items": parsed_items,
        "parse_errors": errors,
        "warnings": warnings,
    }


def parse_announcement_date(value: str) -> str:
    for pattern in ["%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M"]:
        try:
            return datetime.strptime(value.strip(), pattern).replace(tzinfo=IST).isoformat()
        except ValueError:
            pass
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is not None:
            return parsed.isoformat()
    except (ValueError, TypeError):
        pass
    raise ValueError("Announcement publication time is unrecognised; no timestamp was invented.")


def price_probe(company: dict) -> dict:
    import yfinance as yf

    ticker = yf.Ticker(company["symbol"] + ".NS")
    frame = ticker.history(
        period="3mo", interval="1d", auto_adjust=False, actions=True, raise_errors=True
    )
    if frame.empty:
        raise ValueError("Yahoo returned no daily bars.")
    current_ist = datetime.now(IST)
    complete = frame[
        [
            index.date() < current_ist.date()
            or (
                index.date() == current_ist.date()
                and current_ist.time().replace(tzinfo=None)
                >= datetime.strptime("18:00", "%H:%M").time()
            )
            for index in frame.index
        ]
    ]
    complete = complete.dropna(subset=["Close", "Volume"])
    if len(complete) < 21:
        raise ValueError("Fewer than 21 complete daily bars; no volume ratio can be validated.")
    current, previous = complete.iloc[-1], complete.iloc[-2]
    baseline = complete.iloc[-21:-1]["Volume"].mean()
    corporate_actions = (
        bool((complete.iloc[-2:]["Stock Splits"] != 0).any())
        if "Stock Splits" in complete
        else False
    )
    split_in_baseline = (
        bool((complete.iloc[-21:]["Stock Splits"] != 0).any())
        if "Stock Splits" in complete
        else False
    )
    return {
        "provider": "Yahoo Finance via yfinance",
        "ticker": company["symbol"] + ".NS",
        "complete_sessions": len(complete),
        "last_session": complete.index[-1].date().isoformat(),
        "close": float(current["Close"]),
        "volume": int(current["Volume"]),
        "previous_20_mean_volume": float(baseline),
        "volume_ratio": float(current["Volume"] / baseline)
        if baseline and not split_in_baseline
        else None,
        "price_change_pct": None
        if corporate_actions
        else float((current["Close"] / previous["Close"] - 1) * 100),
        "adjustment": "Unadjusted closes; split-affected daily comparison suppressed.",
        "volume_note": "Volume ratio suppressed because a split affects the comparison window."
        if split_in_baseline
        else None,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
