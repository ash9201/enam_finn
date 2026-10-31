"""Opt-in live timings. Uses existing documents/models, records private answers under artifacts."""

import argparse
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from finn import corpus, embeddings, research
from finn.config import load_local_env
from finn.store import open_store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbol")
    parser.add_argument("question")
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    load_local_env()
    os.environ["FINN_ENABLE_SEMANTIC_SEARCH"] = "true"
    spans = []
    started = time.perf_counter()

    def wrap(function, name):
        def run(*a, **kw):
            at = time.perf_counter()
            try:
                return function(*a, **kw)
            finally:
                spans.append(
                    {
                        "name": name,
                        "start_ms": round((at - started) * 1000),
                        "ms": round((time.perf_counter() - at) * 1000),
                    }
                )

        return run

    @contextmanager
    def instruments():
        with (
            patch.object(embeddings, "schedule_backfill"),
            patch.object(
                corpus, "discover_documents", wrap(corpus.discover_documents, "discovery")
            ),
            patch.object(corpus, "fetch_pdf", wrap(corpus.fetch_pdf, "download")),
            patch.object(
                corpus, "extract_document", wrap(corpus.extract_document, "pdf_processing")
            ),
            patch.object(
                research, "ensure_corpus", wrap(research.ensure_corpus, "corpus_check_inclusive")
            ),
            patch.object(research, "generate", wrap(research.generate, "llm_generation")),
            patch.object(research, "validate_answer", wrap(research.validate_answer, "validation")),
            patch.object(
                research,
                "retrieve_with_diagnostics",
                wrap(research.retrieve_with_diagnostics, "retrieval_inclusive"),
            ),
        ):
            yield

    with open_store() as store, instruments():
        result = research.research_company(store, args.symbol, args.question)
        summary = {
            "symbol": args.symbol,
            "label": args.label,
            "seconds": round(time.perf_counter() - started, 3),
            "cached": result["cached"],
            "claims": len(result["claims"]),
            "words": sum(len(c["statement"].split()) for c in result["claims"]),
            "status": result["status"],
            "spans": spans,
            "usage": result.get("usage"),
        }
        output = Path("artifacts/experience-audit")
        output.mkdir(parents=True, exist_ok=True)
        (output / (args.label + ".json")).write_text(
            json.dumps({"summary": summary, "answer": result}, indent=2), encoding="utf-8"
        )
        print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
