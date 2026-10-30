"""Small, generic live-source probes. No seed-company shortcuts or cached fallbacks."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import csv
import io
import re
from urllib.parse import parse_qs, quote, urljoin, urlparse
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import httpx

USER_AGENT = "Mozilla/5.0 (compatible; FINN/0.1; public financial document research)"
IST = timezone(timedelta(hours=5, minutes=30))


def public_client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=45, follow_redirects=True)


def resolve_company(client: httpx.Client, symbol: str) -> dict:
    symbol = symbol.upper().removesuffix(".NS")
    if not re.fullmatch(r"[A-Z0-9&-]{1,30}", symbol):
        raise ValueError("Supply a valid NSE symbol, not a company URL.")
    response = client.get("https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv")
    response.raise_for_status()
    for original in csv.DictReader(io.StringIO(response.text.lstrip('\ufeff'))):
        row = {key.strip(): value.strip() for key, value in original.items() if key}
        if row.get("SYMBOL") == symbol:
            return {"symbol": symbol, "name": row["NAME OF COMPANY"], "isin": row.get("ISIN NUMBER"), "directory_url": str(response.url)}
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
        kind = "annual_report" if title == "annual reports" else "transcript" if title == "concalls" else None
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
                documents[kind].append({
                    "kind": kind, "source_url": url, "discovery_url": str(response.url),
                    "discovery_label": period.group(0) if period else label,
                    "published_at": None, "reporting_period": None,
                    "metadata_note": "Discovery label is not a verified reporting period or publication date.",
                })
    if not all(documents.values()):
        raise ValueError("The company index does not expose both an annual report and a raw transcript; no summary was substituted.")
    return {"company": company, "discovery_url": str(response.url), "documents": documents}


def fetch_pdf(client: httpx.Client, url: str, max_bytes: int = 50 * 1024 * 1024) -> tuple[bytes, str]:
    """Fetch the linked primary document, handling BSE's public HTML PDF wrapper."""
    attempts = [url]
    response = None
    for _ in range(3):
        target = attempts[-1]
        parsed = urlparse(target)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("Primary documents require an HTTPS source URL.")
        with client.stream("GET", target) as streamed:
            streamed.raise_for_status()
            buffer = bytearray()
            for piece in streamed.iter_bytes():
                buffer.extend(piece)
                if len(buffer) > max_bytes:
                    raise ValueError("Document exceeds the 50 MB feasibility download limit.")
            data, final_url = bytes(buffer), str(streamed.url)
            response = httpx.Response(streamed.status_code, headers=streamed.headers, content=data, request=streamed.request)
        if data.lstrip().startswith(b"%PDF-"):
            return data, final_url
        soup = BeautifulSoup(response.text, "html.parser")
        nested = next((node.get("src") or node.get("data") for node in soup.find_all(["iframe", "embed", "object"]) if node.get("src") or node.get("data")), None)
        if nested:
            candidate = urljoin(final_url, nested)
        elif parsed.hostname.endswith("bseindia.com") and "Pname" in parse_qs(parsed.query):
            # Public attachment path referenced by the exchange's own AnnPdfOpen wrapper.
            name = parse_qs(parsed.query)["Pname"][0]
            if not re.fullmatch(r"[A-Za-z0-9-]+\.pdf", name):
                raise ValueError("Unexpected BSE attachment filename.")
            candidate = f"https://www.bseindia.com/xml-data/corpfiling/AttachHis/{name}"
        else:
            raise ValueError("The source returned HTML instead of a PDF; no alternative content was substituted.")
        if candidate in attempts:
            raise ValueError("Document wrapper redirects in a loop.")
        attempts.append(candidate)
    raise ValueError("Could not obtain a primary PDF from the document wrapper.")


def announcement_probe(client: httpx.Client, company: dict) -> dict:
    response = client.get("https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml")
    response.raise_for_status()
    if b"<!DOCTYPE" in response.content.upper() or b"<!ENTITY" in response.content.upper():
        raise ValueError("Unexpected XML declarations in announcement feed.")
    items = ET.fromstring(response.content).findall(".//item")
    matching = []
    normalise = lambda text: re.sub(r"[^a-z0-9]", "", text.lower())
    wanted = normalise(company["name"])
    for item in items:
        if normalise(item.findtext("title") or "") != wanted:
            continue
        raw_date = item.findtext("pubDate") or ""
        published = datetime.strptime(raw_date, "%d-%b-%Y %H:%M:%S").replace(tzinfo=IST).isoformat()
        matching.append({"company": item.findtext("title"), "description": item.findtext("description"), "source_url": item.findtext("link"), "published_at": published})
    return {"source_url": str(response.url), "feed_items": len(items), "company_items": matching, "coverage": "Recent RSS window only; not a complete historical filing archive."}


def price_probe(company: dict) -> dict:
    import yfinance as yf
    ticker = yf.Ticker(company["symbol"] + ".NS")
    frame = ticker.history(period="3mo", interval="1d", auto_adjust=False, actions=True, raise_errors=True)
    if frame.empty:
        raise ValueError("Yahoo returned no daily bars.")
    current_ist = datetime.now(IST)
    complete = frame[[index.date() < current_ist.date() or (index.date() == current_ist.date() and current_ist.time().replace(tzinfo=None) >= datetime.strptime("18:00", "%H:%M").time()) for index in frame.index]]
    complete = complete.dropna(subset=["Close", "Volume"])
    if len(complete) < 21:
        raise ValueError("Fewer than 21 complete daily bars; no volume ratio can be validated.")
    current, previous = complete.iloc[-1], complete.iloc[-2]
    baseline = complete.iloc[-21:-1]["Volume"].mean()
    corporate_actions = bool((complete.iloc[-2:]["Stock Splits"] != 0).any()) if "Stock Splits" in complete else False
    return {
        "provider": "Yahoo Finance via yfinance", "ticker": company["symbol"] + ".NS",
        "complete_sessions": len(complete), "last_session": complete.index[-1].date().isoformat(),
        "close": float(current["Close"]), "volume": int(current["Volume"]),
        "previous_20_mean_volume": float(baseline), "volume_ratio": float(current["Volume"] / baseline) if baseline else None,
        "price_change_pct": None if corporate_actions else float((current["Close"] / previous["Close"] - 1) * 100),
        "adjustment": "Unadjusted closes; split-affected daily comparison suppressed.",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
