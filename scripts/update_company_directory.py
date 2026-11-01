"""Publish a dated NSE equity/name/symbol directory for local frontend search."""

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

from finn.sources import public_client

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://archives.nseindia.com/content/equities/"


def normal(value):
    return "".join(c for c in value.lower() if c.isalnum())


def main():
    sources, tables = [], {}
    with public_client() as client:
        for filename in ["EQUITY_L.csv", "symbolchange.csv", "namechange.csv"]:
            response = client.get(BASE + filename)
            response.raise_for_status()
            rows = [
                {k.strip(): (v or "").strip() for k, v in row.items() if k}
                for row in csv.DictReader(io.StringIO(response.text.lstrip("\ufeff")))
            ]
            if not rows or "<html" in response.text[:100].lower():
                raise ValueError(
                    f"No valid official records in {filename}; existing capture retained."
                )
            tables[filename] = rows
            sources.append(BASE + filename)
    current = {
        row["SYMBOL"]: {
            "symbol": row["SYMBOL"],
            "name": row["NAME OF COMPANY"],
            "isin": row.get("ISIN NUMBER"),
            "aliases": set(),
        }
        for row in tables["EQUITY_L.csv"]
    }
    today = datetime.now(timezone.utc).date()

    def effective(row):
        try:
            return datetime.strptime(row["EFFECTIVE DATE"], "%d-%b-%Y").date() <= today
        except (KeyError, ValueError):
            return False

    changes = [row for row in tables["symbolchange.csv"] if effective(row)]
    changes.sort(key=lambda row: datetime.strptime(row["EFFECTIVE DATE"], "%d-%b-%Y"))
    renamed = {row["OLD SYMBOL"]: row["NEW SYMBOL"] for row in changes}

    def canonical(symbol):
        seen = set()
        while symbol not in current and symbol in renamed and symbol not in seen:
            seen.add(symbol)
            symbol = renamed[symbol]
        return symbol if symbol in current else None

    # Only connected name histories are attached, avoiding reused ticker identities.
    known_names = {symbol: {normal(row["name"])} for symbol, row in current.items()}
    for _ in range(12):
        added = 0
        for row in tables["namechange.csv"]:
            symbol = canonical(row["SYMBOL"])
            if not symbol or not effective(row):
                continue
            old, new = row["OLD NAME OF THE COMPANY"], row["NEW NAME OF THE COMPANY"]
            if normal(new) in known_names[symbol] and normal(old) not in known_names[symbol]:
                current[symbol]["aliases"].add(old)
                known_names[symbol].add(normal(old))
                added += 1
        if not added:
            break
    for row in changes:
        symbol = canonical(row["NEW SYMBOL"])
        if symbol and normal(row["NAME OF THE COMPANY"]) in known_names[symbol]:
            current[symbol]["aliases"].add(row["OLD SYMBOL"])
    for row in current.values():
        row["aliases"] = sorted(row["aliases"])
    output = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "scope": "NSE equity directory; name/symbol histories linked to current listings",
        "companies": sorted(current.values(), key=lambda row: row["symbol"]),
    }
    (ROOT / "frontend/public/company-directory.json").write_text(
        json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf8"
    )
    print(f"Captured {len(current)} current listings with official name/symbol history.")


if __name__ == "__main__":
    main()
