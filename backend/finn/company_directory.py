"""Verified NSE identities, independent of live directory availability during research."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import time
from datetime import UTC, datetime
from threading import Lock
from urllib.parse import urlparse

import httpx

from finn.config import ROOT
from finn.services import DependencyError

SNAPSHOT = ROOT / "frontend/public/company-directory.json"
EQUITY_URLS = [
    "https://archives.nseindia.com/content/equities/EQUITY_L.csv",
    "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
]
REFERENCE_PATH = "company-directory.json"
_cache: dict[str, tuple[float, dict]] = {}
_lock = Lock()


def valid_identity(row):
    return bool(
        isinstance(row, dict)
        and isinstance(row.get("symbol"), str)
        and re.fullmatch(r"[A-Z0-9&-]{1,30}", row["symbol"])
        and isinstance(row.get("name"), str)
        and 2 <= len(row["name"].strip()) <= 250
        and isinstance(row.get("isin"), str)
        and re.fullmatch(r"IN[A-Z0-9]{9}[0-9]", row["isin"])
    )


def validate_snapshot(value):
    if not isinstance(value, dict):
        raise TypeError("Invalid company directory snapshot.")
    checked = datetime.fromisoformat(value["checked_at"])
    if checked.tzinfo is None or checked.timestamp() > time.time() + 86400:
        raise ValueError("Invalid company directory verification date.")
    rows, sources = value["companies"], value["sources"]
    if not isinstance(rows, list) or not 1000 <= len(rows) <= 10000:
        raise ValueError("The company directory is incomplete; last-known-good data retained.")
    if (
        not sources
        or not any(url in EQUITY_URLS for url in sources)
        or not all(
            isinstance(url, str)
            and urlparse(url).scheme == "https"
            and urlparse(url).hostname in {"archives.nseindia.com", "nsearchives.nseindia.com"}
            and urlparse(url).path.startswith("/content/equities/")
            for url in sources
        )
    ):
        raise ValueError("Company identities require official NSE directory provenance.")
    if not all(valid_identity(row) for row in rows):
        raise ValueError("Invalid company identity; last-known-good directory retained.")
    if len({row["symbol"] for row in rows}) != len(rows) or len(
        {row["isin"] for row in rows}
    ) != len(rows):
        raise ValueError("Duplicate company identities; directory not replaced.")
    return value


def directory_snapshot(store=None):
    """A bounded Storage read, then the repository's dated official capture. Never NSE."""
    key = getattr(store, "directory_cache_key", "bundled")
    with _lock:
        cached = _cache.get(key)
        if cached and time.monotonic() - cached[0] < 900:
            return cached[1]
        candidates = [cached[1]] if cached else []
        try:
            candidates.append(validate_snapshot(json.loads(SNAPSHOT.read_text(encoding="utf-8"))))
        except (ValueError, KeyError, TypeError, OSError):
            pass
        if store is not None and hasattr(store, "get_reference_snapshot"):
            try:
                persisted = store.get_reference_snapshot(REFERENCE_PATH)
                if persisted:
                    candidates.append(validate_snapshot(persisted))
            except (DependencyError, ValueError, KeyError, TypeError, OSError):
                # The built-in capture remains verified; do not change its date.
                pass
        if not candidates:
            raise DependencyError("No verified directory snapshot is currently available.")
        selected = max(candidates, key=lambda item: datetime.fromisoformat(item["checked_at"]))
        _cache[key] = (time.monotonic(), selected)
        return selected


def resolve_identity(symbol, *, store=None, known=None):
    symbol = symbol.strip().upper().removesuffix(".NS")
    if not re.fullmatch(r"[A-Z0-9&-]{1,30}", symbol):
        raise ValueError("Supply a valid NSE symbol, not a company URL.")
    if known is None and store is not None:
        rows = store.rows("finn_companies", symbol="eq." + symbol, limit=1)
        known = rows[0] if rows else None
    try:
        snapshot = directory_snapshot(store)
    except DependencyError:
        snapshot = None
    row = (
        next((row for row in snapshot["companies"] if row["symbol"] == symbol), None)
        if snapshot
        else None
    )
    if row:
        if valid_identity(known) and known["isin"] != row["isin"]:
            raise ValueError(
                f"The verified ISIN for {symbol} differs from the stored company. "
                "Research was stopped to avoid mixing company identities."
            )
        return {
            **row,
            "directory_url": next(url for url in snapshot["sources"] if "EQUITY_L.csv" in url),
            "directory_checked_at": snapshot["checked_at"],
            "identity_source": "verified_nse_directory",
        }
    # Existing rows were written by the official-directory resolver, never by the
    # browser's fuzzy search. Preserve them during outages, with honest provenance.
    if valid_identity(known) and known["symbol"] == symbol:
        return {
            "symbol": symbol,
            "name": known["name"],
            "isin": known["isin"],
            "directory_url": EQUITY_URLS[0],
            "directory_checked_at": None,
            "identity_source": "previously_resolved_company",
            "identity_note": "Original directory verification date was not recorded for this legacy identity.",
        }
    if snapshot is None:
        raise ValueError(
            f"NSE symbol {symbol} could not be verified: the directory is unavailable and no previously resolved identity exists."
        )
    raise ValueError(
        f"NSE symbol {symbol} was not found in the verified company directory "
        f"(checked {snapshot['checked_at'][:10]}). Check the exact symbol or retry after a directory refresh. "
        "No similarly named company was substituted."
    )


def refreshed_snapshot(client, previous):
    """Fetch authoritative current listings; carry aliases only across the same ISIN."""
    failures = []
    for url in EQUITY_URLS:
        try:
            response = client.get(url, timeout=12)
            if response.is_error:
                failures.append(f"{urlparse(url).hostname}: HTTP {response.status_code}")
                continue
            if str(response.url).split("?")[0] not in EQUITY_URLS:
                raise ValueError("Directory response did not remain on an official NSE source.")
            original = csv.DictReader(io.StringIO(response.text.lstrip("\ufeff")))
            if not {"SYMBOL", "NAME OF COMPANY", "ISIN NUMBER"} <= {
                field.strip() for field in original.fieldnames or []
            }:
                raise ValueError("Required NSE directory columns are missing.")
            old_by_isin = {row["isin"]: row for row in previous["companies"]}
            companies = []
            for item in original:
                item = {key.strip(): (value or "").strip() for key, value in item.items() if key}
                companies.append(
                    {
                        "symbol": item["SYMBOL"],
                        "name": item["NAME OF COMPANY"],
                        "isin": item["ISIN NUMBER"],
                        "series": item.get("SERIES"),
                        "listing_date": item.get("DATE OF LISTING"),
                    }
                )
            symbols = {row["symbol"] for row in companies}
            for row in companies:
                old = old_by_isin.get(row["isin"], {})
                aliases = set(old.get("aliases", []))
                if old.get("name") and old["name"] != row["name"]:
                    aliases.add(old["name"])
                if old.get("symbol") and old["symbol"] not in symbols:
                    aliases.add(old["symbol"])
                row["aliases"] = sorted(aliases)
            checked = datetime.now(UTC).isoformat()
            value = validate_snapshot(
                {
                    "checked_at": checked,
                    "sources": [
                        url,
                        *[source for source in previous["sources"] if "EQUITY_L.csv" not in source],
                    ],
                    "source_checks": {
                        **previous.get(
                            "source_checks",
                            {source: previous["checked_at"] for source in previous["sources"]},
                        ),
                        url: checked,
                    },
                    "scope": previous.get("scope", "NSE equity directory"),
                    "companies": sorted(companies, key=lambda row: row["symbol"]),
                }
            )
            if len(value["companies"]) < len(previous["companies"]) * 0.9:
                raise ValueError(
                    "Directory unexpectedly shrank by more than 10%; retained last-known-good data."
                )
            return value
        except (ValueError, KeyError, TypeError, csv.Error):
            failures.append(f"{urlparse(url).hostname}: invalid directory response")
        except httpx.HTTPError as exc:
            # Do not leak request headers or credential-bearing URLs in diagnostics.
            failures.append(f"{urlparse(url).hostname}: {type(exc).__name__}")
    raise ValueError(
        "NSE directory refresh unavailable; last-known-good snapshot retained. "
        + "; ".join(failures)
    )


def refresh_directory(store, client, *, force=False):
    previous = directory_snapshot(store)
    # Bootstrap durable storage with its ORIGINAL provenance/date, before any fetch.
    if store.get_reference_snapshot(REFERENCE_PATH) is None:
        store.put_reference_snapshot(REFERENCE_PATH, previous)
    status = store.get_reference_snapshot("company-directory-refresh.json")
    if not force and status:
        try:
            attempted = datetime.fromisoformat(status["attempted_at"])
            if 0 <= (datetime.now(UTC) - attempted).total_seconds() < 86400:
                return {
                    "state": "already_attempted",
                    "last_attempt": status,
                    "checked_at": previous["checked_at"],
                }
        except (KeyError, ValueError, TypeError):
            pass
    checked = datetime.fromisoformat(previous["checked_at"])
    if not force and (datetime.now(UTC) - checked).total_seconds() < 86400:
        return {
            "state": "current",
            "checked_at": previous["checked_at"],
            "companies": len(previous["companies"]),
        }
    try:
        current = refreshed_snapshot(client, previous)
    except ValueError as exc:
        store.put_reference_snapshot(
            "company-directory-refresh.json",
            {
                "attempted_at": datetime.now(UTC).isoformat(),
                "state": "failed",
                "error": str(exc),
                "retained_checked_at": previous["checked_at"],
            },
        )
        raise
    store.put_reference_snapshot(REFERENCE_PATH, current)
    store.put_reference_snapshot(
        "company-directory-refresh.json",
        {
            "attempted_at": datetime.now(UTC).isoformat(),
            "state": "completed",
            "checked_at": current["checked_at"],
        },
    )
    with _lock:
        _cache.pop(getattr(store, "directory_cache_key", "bundled"), None)
    return {
        "state": "refreshed",
        "checked_at": current["checked_at"],
        "companies": len(current["companies"]),
    }


def main():
    from finn.config import load_local_env
    from finn.sources import public_client
    from finn.store import open_store

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    load_local_env()
    with open_store() as store, public_client() as client:
        try:
            print(json.dumps(refresh_directory(store, client, force=args.force)))
        except (ValueError, DependencyError) as exc:
            print(str(exc))
            raise SystemExit(1) from None


if __name__ == "__main__":
    main()
