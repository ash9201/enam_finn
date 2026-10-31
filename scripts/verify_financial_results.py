"""Opt-in, original-source acceptance cases. No financial values are seeded."""

import argparse
import json
from pathlib import Path

from finn.config import load_local_env
from finn.financials import analyse_results
from finn.store import open_store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish these verified prepared financial outputs only.",
    )
    parser.add_argument(
        "--followup",
        action="store_true",
        help="Verify one private cross-document research follow-up (uses Gemini if uncached).",
    )
    args = parser.parse_args()
    load_local_env()
    output = Path("artifacts/financial-results")
    output.mkdir(parents=True, exist_ok=True)
    with open_store() as store:
        prepared = {}
        for symbol in ["POLYCAB", "CCL"]:
            result = analyse_results(store, symbol, publish=False)
            data = result["financial_results"]
            assert data["periods"] == {
                "latest": "2026-09-30",
                "previous": "2026-06-30",
                "year_ago": "2025-09-30",
            }, (
                "Source period changed; review the new original statement before updating this dated acceptance case."
            )
            rows = {r["metric"]: r for r in data["bases"]["consolidated"]["rows"]}
            assert not rows["EBITDA"]["figures"], (
                "Reported EBITDA now exists: inspect its definition before updating this case."
            )
            if symbol == "POLYCAB":
                assert [
                    rows["Revenue"]["figures"][k]["value"]
                    for k in ["latest", "previous", "year_ago"]
                ] == ["98989.01", "82097.32", "64772.11"]
                assert (
                    rows["Revenue"]["qoq"]["absolute"] == "16891.69"
                    and rows["Revenue"]["yoy"]["percent"] == "52.83"
                )
                assert rows["PBT"]["figures"]["latest"]["value"] == "13062.20"
                assert rows["PAT"]["figures"]["latest"]["value"] == "9899.97"
            else:
                assert (
                    "latest" not in rows["Revenue"]["figures"]
                    and rows["Revenue"]["qoq"]["absolute"] is None
                )
                assert (
                    "previous" not in rows["PBT"]["figures"]
                    and rows["PBT"]["qoq"]["absolute"] is None
                )
                assert (
                    rows["PAT"]["figures"]["latest"]["value"] == "13010.97"
                    and rows["PAT"]["yoy"]["percent"] == "29.00"
                )
            again = analyse_results(store, symbol)
            assert again["cached"] and again["id"] == result["id"]
            if args.publish:
                result = analyse_results(store, symbol, publish=True)
            (output / (symbol + "-analysis.json")).write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
            prepared[symbol] = result
            print(
                json.dumps(
                    {
                        "symbol": symbol,
                        "status": result["status"],
                        "filings": len(data["sources"]),
                        "source_pages": sorted(
                            {c["citation"]["pdf_page"] for c in result["claims"]}
                        ),
                        "claims": len(result["claims"]),
                        "withheld_cells": len(data["rejected_cells"]),
                        "cached_repeat": True,
                        "published": args.publish,
                    }
                ),
                flush=True,
            )
        if args.followup:
            from finn.research import research_company

            parent = prepared["POLYCAB"]
            index = parent["financial_results"]["bases"]["consolidated"]["rows"][0]["figures"][
                "latest"
            ]["claim_index"]
            selected = parent["claims"][index]
            answer = research_company(
                store,
                "POLYCAB",
                "What did management say about demand or margin pressures that could provide context for this result? Distinguish commentary from proof of causation.",
                context_reference={
                    "research_id": parent["id"],
                    "citation_id": selected["citation"]["id"],
                    "claim_index": index,
                    "intent": "question",
                },
            )
            (output / "followup.json").write_text(json.dumps(answer, indent=2), encoding="utf-8")
            assert answer["status"] == "answered" and any(
                c["citation"]["document_id"] != selected["citation"]["document_id"]
                for c in answer["claims"]
            ), (
                "No independent supported narrative answer; inspect the artifact rather than substituting a demo response."
            )
            print(
                json.dumps(
                    {
                        "financial_followup": answer["status"],
                        "claims": len(answer["claims"]),
                        "other_documents": answer["investigation"]["other_documents_retrieved"],
                    }
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
