"""Opt-in real-source checks for the investor QA cases. Publication is explicit."""

import argparse
import json
import time
from pathlib import Path

from finn.comparison import COMPARISON_QUESTION
from finn.config import load_local_env
from finn.disclosed_context import add_disclosed_context
from finn.financial_insights import with_performance
from finn.financials import QUESTION
from finn.management_readings import concrete_comparison
from finn.research import research_company
from finn.store import open_store

CASES = {
    "INFY": "Explain Infosys's business model in detail. What services does it provide, who are its main customers, and how does it generate revenue?",
    "M&M": "Explain Mahindra & Mahindra's major business segments, their main products and services, and how these businesses contribute to the company's overall operations.",
    "CCL": "What are the main factors affecting CCL Products' profitability, and what has management said about demand, production capacity, and future growth?",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    load_local_env()
    output = Path("artifacts/targeted-fixes")
    output.mkdir(exist_ok=True, parents=True)
    summary = []
    with open_store() as store:
        for symbol, question in CASES.items():
            started = time.perf_counter()
            result = research_company(store, symbol, question, publish=args.publish)
            assert result["status"] == "answered"
            coverage = {c["aspect"]: c for c in result["question_coverage"]}
            if symbol == "M&M":
                assert (
                    coverage["contribution"]["status"] != "covered"
                    and coverage["contribution"]["note"]
                )
            else:
                assert all(c["status"] == "covered" for c in coverage.values())
            (output / f"{symbol}-improved.json").write_text(
                json.dumps(result, indent=2), encoding="utf8"
            )
            summary.append(
                {
                    "symbol": symbol,
                    "claims": len(result["claims"]),
                    "seconds": round(time.perf_counter() - started, 2),
                    "coverage": result["question_coverage"],
                }
            )
        for symbol in ["NTPC", "SUNPHARMA", "M&M"]:
            row = store.rows(
                "finn_research_cache",
                symbol="eq." + symbol,
                question="eq." + QUESTION,
                order="created_at.desc",
                limit=1,
            )[0]
            result = with_performance(row["result"])
            if symbol == "SUNPHARMA":
                result = add_disclosed_context(store, result)
            (output / f"{symbol}-financial.json").write_text(
                json.dumps(result, indent=2), encoding="utf8"
            )
            if args.publish:
                store.patch(
                    "finn_research_cache",
                    {"result": result, "is_public": True},
                    id="eq." + row["id"],
                )
        row = store.rows(
            "finn_research_cache",
            symbol="eq.KPITTECH",
            question="eq." + COMPARISON_QUESTION,
            order="created_at.desc",
            limit=1,
        )[0]
        result = concrete_comparison(row["result"])
        assert (
            result["comparison"]["verdict"] == "not_yet_assessable"
            and "17.2%" in result["comparison"]["later"]["statement"]
        )
        (output / "KPITTECH-comparison.json").write_text(
            json.dumps(result, indent=2), encoding="utf8"
        )
        if args.publish:
            store.patch(
                "finn_research_cache", {"result": result, "is_public": True}, id="eq." + row["id"]
            )
    (output / "verified-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf8")
    print(json.dumps({"research_cases": summary, "published": args.publish}), flush=True)


if __name__ == "__main__":
    main()
