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
        inventory = store.rpc(
            "finn_embedding_inventory",
            {"p_model": embeddings.model_name(), "p_version": embeddings.VERSION},
        )
        pending = [c for c in inventory["companies"] if c["total"] > c["ready"]]
        # Finish nearly complete watchlist indexes first; then other requested
        # companies. Includes quarterly-only corpora, without indexing the NSE universe.
        pending.sort(
            key=lambda c: (not c["portfolio"], -c["ready"] / c["total"], c["total"], c["symbol"])
        )
        print(
            json.dumps(
                {"pending_companies": len(pending), "database_bytes": inventory["database_bytes"]}
            ),
            flush=True,
        )
        for company in pending:
            symbol = company["symbol"]
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
