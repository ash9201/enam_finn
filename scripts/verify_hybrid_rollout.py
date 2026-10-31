"""Opt-in rollout smoke test against real Supabase/Gemini; Render is not modified."""

import json
import os
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from finn import embeddings, retrieval
from finn.config import load_local_env
from finn.research import research_company
from finn.store import open_store

OUTPUT = Path("artifacts/hybrid-rollout")
QUESTIONS = {
    "CCL": "Which coffee products and customer channels does CCL describe in its primary documents?",
    "GOKEX": "Which businesses buy Gokaldas Exports products, and what type of apparel does it manufacture?",
}


def write(name, value):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(json.dumps(value, indent=2), encoding="utf-8")


def answer_from_current_index(store, symbol, question):
    # Verification spends query/generation allowance only. Explicit backfill is a
    # separate operator action; do not compete for bulk quota after the next reset.
    with patch("finn.embeddings.schedule_backfill"):
        return research_company(store, symbol, question)


def main():
    load_local_env()
    # Process-only opt-in. Never edits .env.local or production configuration.
    os.environ["FINN_ENABLE_SEMANTIC_SEARCH"] = "true"
    summary = {"settings": asdict(retrieval.SETTINGS), "companies": {}, "faults": {}}
    with open_store() as store:
        for symbol, question in QUESTIONS.items():
            index = embeddings.status(store, symbol)
            if not index["total"] or index["ready"] != index["total"]:
                raise SystemExit(f"{symbol} is incomplete; no partial hybrid test substituted.")
            first = retrieval.retrieve_with_diagnostics(store, symbol, question)
            assert first["mode"] == "hybrid" and first["semantic_candidates"]
            assert first["profile"]["settings"] == asdict(retrieval.SETTINGS)
            repeated = retrieval.retrieve_with_diagnostics(store, symbol, question)
            assert repeated["query_embedding_cached"] and repeated["embedding_provider_calls"] == 0
            answer = answer_from_current_index(store, symbol, question)
            assert (
                answer["retrieval_mode"] == "hybrid"
                and answer["status"] == "answered"
                and answer["claims"]
            )
            again = answer_from_current_index(store, symbol, question)
            assert again["cached"] and again["id"] == answer["id"]
            allowed = set(
                store.rows("finn_companies", symbol="eq." + symbol, select="manifest")[0][
                    "manifest"
                ]
            )
            assert all(
                c["citation"]["document_id"] in allowed and c["citation"]["quote"]
                for c in answer["claims"]
            )
            write(symbol + "-hybrid-answer.json", answer)
            summary["companies"][symbol] = {
                "ready": index["ready"],
                "total": index["total"],
                "mode": first["mode"],
                "first_query_provider_calls": first["embedding_provider_calls"],
                "first_query_cached": first["query_embedding_cached"],
                "repeated_query_provider_calls": repeated["embedding_provider_calls"],
                "answer_claims": len(answer["claims"]),
                "answer_cache_reused": True,
                "retrieval_ms": first["latency_ms"],
            }
            print(json.dumps({"symbol": symbol, **summary["companies"][symbol]}), flush=True)

        for symbol in ["INFY", "POLYCAB"]:
            profile = retrieval.retrieval_profile(store, symbol)
            assert profile["state"] == "indexing" and profile["mode"] == "keyword"
            result = retrieval.retrieve_with_diagnostics(
                store, symbol, "Explain the core business and its main services or products."
            )
            assert result["mode"] == "keyword" and result["fallback_reason"] == "index_incomplete"
            assert result["embedding_provider_calls"] == 0 and result["evidence"]
            summary["companies"][symbol] = {
                "ready": profile["index"]["ready"],
                "total": profile["index"]["total"],
                "mode": result["mode"],
                "fallback_reason": result["fallback_reason"],
                "embedding_provider_calls": 0,
            }
        # Exercise a real incomplete-company answer once, not just status inspection.
        partial = answer_from_current_index(
            store,
            "INFY",
            "Describe Infosys business activities from the available primary company documents.",
        )
        assert (
            partial["retrieval_mode"] == "keyword"
            and partial["retrieval"]["fallback_reason"] == "index_incomplete"
        )
        assert partial["status"] == "answered" and partial["claims"]
        write("INFY-fallback-answer.json", partial)
        summary["companies"]["INFY"]["answer_claims"] = len(partial["claims"])

        # Faults are deliberately injected locally; PostgreSQL keyword reads remain real.
        question = QUESTIONS["CCL"]
        with patch(
            "finn.retrieval.embeddings.EmbeddingClient",
            side_effect=embeddings.EmbeddingUnavailable("provider_connection"),
        ):
            failure = retrieval.retrieve_with_diagnostics(store, "CCL", question)
        assert (
            failure["mode"] == "keyword"
            and failure["fallback_reason"] == "semantic_unavailable"
            and failure["evidence"]
        )
        summary["faults"]["simulated_provider_failure"] = {
            "mode": failure["mode"],
            "reason": failure["fallback_reason"],
            "evidence_count": len(failure["evidence"]),
        }
        original_rpc = store.rpc

        def unavailable(name, values):
            if name == "finn_semantic_search":
                from finn.services import DependencyError

                raise DependencyError("Locally simulated semantic SQL failure")
            return original_rpc(name, values)

        with patch.object(store, "rpc", side_effect=unavailable):
            failure = retrieval.retrieve_with_diagnostics(store, "CCL", question)
        assert (
            failure["mode"] == "keyword"
            and failure["fallback_reason"] == "semantic_unavailable"
            and failure["evidence"]
        )
        summary["faults"]["simulated_semantic_rpc_failure"] = {
            "mode": failure["mode"],
            "reason": failure["fallback_reason"],
            "evidence_count": len(failure["evidence"]),
        }
        os.environ["FINN_ENABLE_SEMANTIC_SEARCH"] = "false"
        rollback = retrieval.retrieve_with_diagnostics(store, "CCL", question)
        assert (
            rollback["mode"] == "keyword"
            and rollback["embedding_provider_calls"] == 0
            and rollback["fallback_reason"] is None
        )
        summary["rollback"] = {"mode": rollback["mode"], "embedding_provider_calls": 0}
    write("verification.json", summary)
    embeddings.stop_background()
    print(
        json.dumps({"verification": "passed", "output": str(OUTPUT / "verification.json")}),
        flush=True,
    )


if __name__ == "__main__":
    main()
