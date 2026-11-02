"""Idempotent rating-classification repair. Dry run by default; immutable IDs remain intact."""

import argparse
import json

from finn.briefing import classify_filing
from finn.config import load_local_env
from finn.store import open_store


def repair_ratings(store, *, apply=False):
    changes = []
    offset = 0
    while True:
        rows = store.rows(
            "finn_filings",
            category="in.(credit_rating,unclassified)",
            select="id,symbol,description,category,priority,review_reason",
            order="id",
            limit=500,
            offset=offset,
        )
        for row in rows:
            category, priority, reason = classify_filing(row["description"])
            if row["category"] != "credit_rating" and category != "credit_rating":
                continue
            target = {"category": category, "priority": priority, "review_reason": reason}
            if all(row[k] == v for k, v in target.items()):
                continue
            changes.append(
                {
                    "id": row["id"],
                    "symbol": row["symbol"],
                    "before": {k: row[k] for k in target},
                    "after": target,
                }
            )
        if len(rows) < 500:
            break
        offset += len(rows)
    # Read the full candidate set before changing categories, avoiding pagination skips.
    if apply:
        for change in changes:
            store.patch(
                "finn_filings",
                change["after"],
                id="eq." + change["id"],
                category="eq." + change["before"]["category"],
                priority="eq." + str(change["before"]["priority"]),
            )
    return {"applied": apply, "changes": changes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    load_local_env()
    with open_store() as store:
        print(json.dumps(repair_ratings(store, apply=args.apply), indent=2))


if __name__ == "__main__":
    main()
