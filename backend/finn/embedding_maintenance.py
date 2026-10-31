"""Daily bounded maintenance using the same embedding pipeline as research ingestion."""

import argparse
import json

from finn import embeddings
from finn.config import load_local_env
from finn.store import open_store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-batches", type=int, default=40)
    args = parser.parse_args()
    load_local_env()
    if not 1 <= args.max_batches <= 60:
        raise ValueError("Use between 1 and 60 bounded batches.")
    with open_store() as store:
        companies = store.rows(
            "finn_companies", select="symbol,manifest,portfolio", order="portfolio.desc,symbol"
        )
        available = [c["symbol"] for c in companies if c.get("manifest")]
        symbols = list(
            dict.fromkeys([s for s in ["INFY", "POLYCAB", "CCL", *available] if s in available])
        )
        for symbol in symbols:
            status = embeddings.status(store, symbol)
            if status["total"] == status["ready"]:
                continue
            result = embeddings.backfill(store, symbol, max_batches=args.max_batches, wait=True)
            print(
                json.dumps(
                    {
                        "symbol": symbol,
                        "ready": result["ready"],
                        "total": result["total"],
                        "reason": result["reason"],
                        "provider_calls": result["provider_calls"],
                    }
                ),
                flush=True,
            )
            if result["reason"] in ["daily_budget", "provider_daily_budget"]:
                break


if __name__ == "__main__":
    main()
