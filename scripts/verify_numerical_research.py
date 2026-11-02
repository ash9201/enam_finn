"""Opt-in primary-document numerical smoke check; no generation or embedding calls.

Uses existing TMCV/V2RETAIL corpora and writes ignored, real browser fixtures. Values
are discovered and validated, never hardcoded. Missing coverage is reported explicitly.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

from finn.config import load_local_env
from finn.evidence import resolve_context
from finn.metric_research import complete_numerical_answer, numerical_research
from finn.metric_registry import financial_intent
from finn.store import open_store

OUTPUT = Path(__file__).resolve().parents[1] / "artifacts/financial-metrics"


def write(name, value):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / (name + ".json")).write_text(json.dumps(value, indent=2), encoding="utf-8")


def main():
    load_local_env()
    # Process-only verification setting. Production rollout settings are untouched.
    os.environ["FINN_ENABLE_SEMANTIC_SEARCH"] = "false"
    cases = [
        ("TMCV", "debt to equity ratio", "TMCV-bare"),
        ("TMCV", "Debt to equity ratio FY2026 consolidated", "TMCV-numerical"),
        ("TMCV", "Debt to equity ratio FY2026 standalone", "TMCV-standalone"),
        ("V2RETAIL", "net profit margin quarterly", "V2RETAIL-margin"),
        ("TMCV", "ROIC FY2019", "TMCV-unavailable"),
    ]
    summary = []
    with open_store() as store:
        for symbol, question, name in cases:
            documents = store.rows(
                "finn_search_documents",
                symbol="eq." + symbol,
                select="id",
                kind="eq.annual_report" if symbol == "TMCV" else "eq.quarterly_results",
                limit=1,
            )
            if not documents:
                raise SystemExit(
                    f"{symbol}: collect its primary documents before this bounded verification; no fresh source ingestion was started."
                )
            answer = numerical_research(store, symbol, question)
            assert complete_numerical_answer(
                financial_intent(question), answer["financial_metrics"]["results"]
            )
            write(name, answer)
            contexts = []
            for index, claim in enumerate(answer["claims"]):
                context, anchor = resolve_context(
                    store,
                    symbol,
                    {
                        "research_id": answer["id"],
                        "citation_id": claim["citation"]["id"],
                        "claim_index": index,
                    },
                )
                contexts.append({"context": context, "anchor": anchor})
            write(name + "-evidence", contexts)
            record = {
                "symbol": symbol,
                "question": question,
                "status": answer["status"],
                "results": [
                    {
                        k: r.get(k)
                        for k in [
                            "name",
                            "status",
                            "value",
                            "unit",
                            "period_end",
                            "basis",
                            "method",
                        ]
                    }
                    for r in answer["financial_metrics"]["results"]
                ],
                "verified_source_contexts": len(contexts),
            }
            summary.append(record)
            print(json.dumps(record), flush=True)
        with patch.object(
            store, "get_pdf", side_effect=AssertionError("A cached alias reread its PDF")
        ):
            repeat = numerical_research(store, "TMCV", "D/E", cached_only=True)
            assert repeat and repeat["cached"]
        write(
            "verification",
            {
                "cases": summary,
                "warm_alias_reused": True,
                "generation_calls": 0,
                "embedding_calls": 0,
            },
        )


if __name__ == "__main__":
    main()
