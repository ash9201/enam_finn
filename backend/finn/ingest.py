"""Run the exact same company pipeline as on-demand research, without public API access.

python -m finn.ingest --symbol INFY --publish
Only use --portfolio after one complete company answer has passed acceptance.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from finn.config import ROOT, load_local_env
from finn.research import DEFAULT_QUESTION, research_company
from finn.sources import public_client, resolve_company
from finn.store import open_store

PORTFOLIO = {
    "RELIANCE": "Energy & retail",
    "INFY": "IT services",
    "HDFCBANK": "Banking",
    "LT": "Engineering",
    "M&M": "Automotive",
    "BHARTIARTL": "Telecommunications",
    "SUNPHARMA": "Pharmaceuticals",
    "ITC": "Consumer goods",
    "NTPC": "Power",
    "TATASTEEL": "Metals",
    "TITAN": "Consumer discretionary",
    "POLYCAB": "Electrical equipment",
    "KPITTECH": "Automotive software",
    "APLAPOLLO": "Industrial products",
    "CCL": "Consumer exports",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish this prepared answer for anonymous cache reads.",
    )
    parser.add_argument("--portfolio", action="store_true")
    args = parser.parse_args()
    load_local_env()
    with open_store() as store:
        if args.portfolio:
            ready = store.rows(
                "finn_research_cache", symbol="eq.INFY", is_public="eq.true", limit=1
            )
            if not ready or not ready[0]["result"].get("claims"):
                raise SystemExit(
                    "First verify and publish the one-company INFY answer before expanding the portfolio."
                )
            with public_client() as client:
                for symbol, sector in PORTFOLIO.items():
                    company = resolve_company(client, symbol)
                    existing = store.rows("finn_companies", symbol="eq." + symbol, limit=1)
                    values = {
                        "symbol": symbol,
                        "name": company["name"],
                        "isin": company["isin"],
                        "sector": sector,
                        "portfolio": True,
                    }
                    if existing:
                        store.patch("finn_companies", values, symbol="eq." + symbol)
                    else:
                        store.upsert("finn_companies", [values], conflict="symbol")
                    print(f"Portfolio company verified: {symbol}", flush=True)
        if args.symbol:
            symbol = args.symbol.upper().removesuffix(".NS")
            result = research_company(
                store,
                symbol,
                args.question,
                refresh=args.refresh,
                publish=args.publish,
                progress=lambda stage: print(f"[{symbol}] {stage}", flush=True),
            )
            output = ROOT / "artifacts" / "milestone-1"
            output.mkdir(parents=True, exist_ok=True)
            (output / f"{symbol}-research.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(
                f"{symbol}: {result['status']}; {len(result['claims'])} source-backed claims; cached={result['cached']}",
                flush=True,
            )
            if not result["claims"]:
                raise SystemExit(1)


if __name__ == "__main__":
    main()
