"""Capture actual stored answers for bounded frontend regression checks; never publish them."""

import json
from pathlib import Path

from finn.config import load_local_env
from finn.store import open_store

OVERVIEW = "Explain the core business and its main services or products."
RESULTS = "Compare the latest reported quarterly Revenue, EBITDA, PBT and PAT with the previous quarter and year-ago quarter."
COMPARISON = "Trace one earlier management statement against later earnings-call evidence."
QUESTIONS = {
    OVERVIEW: "overview",
    RESULTS: "results",
    COMPARISON: "comparison",
    "What did management say about demand and growth?": "outlook",
    "What are the main risks discussed in the annual report?": "risks",
}


def main():
    load_local_env()
    output = Path(__file__).resolve().parents[1] / "artifacts/research-redesign"
    output.mkdir(parents=True, exist_ok=True)
    captures = {}
    with open_store() as store:
        for symbol in ["INFY", "NTPC", "SUNPHARMA", "CCL"]:
            for row in store.rows(
                "finn_research_cache",
                symbol="eq." + symbol,
                select="result,is_public",
                order="created_at.desc",
                limit=100,
            ):
                answer = row["result"]
                kind = QUESTIONS.get(answer["question"])
                if row["is_public"] and kind:
                    captures.setdefault(symbol + ":" + kind, answer)
                if symbol == "CCL" and kind in {"outlook", "risks"}:
                    captures.setdefault(symbol + ":" + answer["question"], answer)
                if (
                    symbol == "NTPC"
                    and answer.get("financial_results")
                    and len(answer["financial_results"]["bases"]) == 1
                ):
                    captures.setdefault("NTPC:one-basis", answer)
    (output / "fixtures.json").write_text(json.dumps(captures, indent=2), encoding="utf8")
    print(
        f"Captured {len(captures)} real stored answers under ignored artifacts; source dates preserved."
    )


if __name__ == "__main__":
    main()
