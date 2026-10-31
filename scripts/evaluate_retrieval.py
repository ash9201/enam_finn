"""Opt-in live retrieval evaluation. Private passages stay in ignored artifacts/."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import itertools
import json
import os
from pathlib import Path
import statistics
import time

from finn.config import load_local_env
from finn import embeddings, retrieval
from finn.research import PROMPT_VERSION, DraftAnswer, generate, validate_answer
from finn.store import open_store

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts/retrieval"
CASES = ROOT / "evals/retrieval_cases.json"
ORIGINAL = retrieval.RetrievalSettings(
    candidates=30,
    limit=10,
    rrf_k=60,
    semantic_weight=1.0,
    page_cap=2,
    document_cap=4,
    adaptive_document_cap=False,
)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def recall(case, evidence, k):
    gold = {(r["document_id"], r["pdf_page"]) for r in case["reference_pages"]}
    found = {(r["document_id"], r["pdf_page"]) for r in evidence[:k]}
    return len(gold & found) / len(gold) if gold else None


def ranked(record, settings, strategy):
    keyword = record["keyword_candidates"][: settings.candidates]
    semantic = record["semantic_candidates"][: settings.candidates]
    candidates = (
        retrieval.reciprocal_rank_fusion(
            keyword, semantic, k=settings.rrf_k, semantic_weight=settings.semantic_weight
        )
        if strategy == "hybrid"
        else keyword
    )
    return retrieval.diversify(candidates, settings)


def metrics(cases, records, settings, strategy, split):
    selected = [c for c in cases if c["split"] == split and c["id"] in records]
    return {
        f"recall_at_{k}": round(
            statistics.mean(
                recall(c, ranked(records[c["id"]], settings, strategy), k) for c in selected
            ),
            4,
        )
        for k in [5, 10]
    } | {"cases": len(selected)}


def collect(cases, symbols):
    path = ARTIFACTS / "rankings.json"
    records = read(path) if path.exists() else {}
    with open_store() as store:
        for case in cases:
            if symbols and case["symbol"] not in symbols:
                continue
            if case["id"] in records:
                continue
            index = embeddings.status(store, case["symbol"])
            if index["ready"] != index["total"] or not index["total"]:
                print(case["id"], "SKIPPED: incomplete index", flush=True)
                continue
            manifest = store.rows(
                "finn_companies", symbol="eq." + case["symbol"], select="manifest"
            )[0]["manifest"]
            if any(ref["document_id"] not in manifest for ref in case["reference_pages"]):
                raise RuntimeError("Reference source version is no longer active: " + case["id"])
            common = dict(settings=retrieval.RetrievalSettings(candidates=60), **case["filters"])
            keyword = retrieval.retrieve_with_diagnostics(
                store, case["symbol"], case["question"], strategy="keyword", **common
            )
            hybrid = retrieval.retrieve_with_diagnostics(
                store, case["symbol"], case["question"], strategy="hybrid", **common
            )
            if hybrid["mode"] != "hybrid":
                raise RuntimeError(
                    "Hybrid unavailable; no keyword result substituted in evaluation: " + case["id"]
                )
            warm = retrieval.retrieve_with_diagnostics(
                store, case["symbol"], case["question"], strategy="hybrid", **common
            )
            if warm["mode"] != "hybrid":
                raise RuntimeError("Warm hybrid unavailable: " + case["id"])
            record = {
                **hybrid,
                "keyword_latency_ms": keyword["latency_ms"],
                "hybrid_first_latency_ms": hybrid["latency_ms"],
                "hybrid_warm_latency_ms": warm["latency_ms"],
                "warm_embedding_provider_calls": warm.get("embedding_provider_calls"),
                "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            # Both candidate lists need final resolved document URLs for QA replay.
            ids = ",".join(
                {
                    r["document_id"]
                    for r in record["keyword_candidates"] + record["semantic_candidates"]
                }
            )
            urls = (
                {
                    r["id"]: r["final_url"]
                    for r in store.rows(
                        "finn_documents", id="in.(" + ids + ")", select="id,final_url"
                    )
                }
                if ids
                else {}
            )
            for branch in ["keyword_candidates", "semantic_candidates"]:
                for row in record[branch]:
                    row["document_url"] = urls.get(row["document_id"], row["source_url"])
            records[case["id"]] = record
            write(path, records)
            print(case["id"], "collected", flush=True)


def tune(cases):
    records = {
        key: value
        for key, value in read(ARTIFACTS / "rankings.json").items()
        if key in {c["id"] for c in cases}
    }
    positives = [c for c in cases if c["split"] != "negative"]
    if any(c["id"] not in records for c in positives):
        raise RuntimeError("Collect every positive case before tuning.")
    grid = []
    for candidates, rrf_k, weight in itertools.product([30, 60], [10, 60], [0.5, 1.0, 2.0]):
        settings = retrieval.RetrievalSettings(
            candidates=candidates, rrf_k=rrf_k, semantic_weight=weight
        )
        scores = metrics(cases, records, settings, "hybrid", "dev")
        grid.append({"settings": asdict(settings), "dev": scores})
    # Held-out labels never enter parameter selection. Prefer fewer candidates,
    # equal weights and conventional k=60 when development scores tie.
    grid.sort(
        key=lambda x: (
            -x["dev"]["recall_at_10"],
            -x["dev"]["recall_at_5"],
            x["settings"]["candidates"],
            abs(x["settings"]["semantic_weight"] - 1),
            abs(x["settings"]["rrf_k"] - 60),
        )
    )
    chosen = retrieval.RetrievalSettings(**grid[0]["settings"])
    baseline = ORIGINAL
    report = {
        "cases_version": read(CASES)["version"],
        "executed_case_ids": [c["id"] for c in cases],
        "selected_settings": asdict(chosen),
        "grid_dev_only": grid,
        "results": {},
    }
    for label, settings, strategy in [
        ("keyword_original", baseline, "keyword"),
        ("keyword_matched", chosen, "keyword"),
        ("hybrid", chosen, "hybrid"),
    ]:
        report["results"][label] = {
            split: metrics(cases, records, settings, strategy, split)
            for split in ["dev", "heldout"]
        }
    report["case_scores"] = {
        c["id"]: {
            method: {
                f"recall_at_{k}": recall(c, ranked(records[c["id"]], settings, strategy), k)
                for k in [5, 10]
            }
            for method, settings, strategy in [
                ("keyword", baseline, "keyword"),
                ("keyword_matched", chosen, "keyword"),
                ("hybrid", chosen, "hybrid"),
            ]
        }
        for c in positives
    }
    report["latency_ms_median_candidates_60"] = {
        key: round(statistics.median(r[key] for r in records.values()), 2)
        for key in ["keyword_latency_ms", "hybrid_first_latency_ms", "hybrid_warm_latency_ms"]
    }
    write(ARTIFACTS / "metrics.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "grid_dev_only"}, indent=2))


def answers(cases):
    records = read(ARTIFACTS / "rankings.json")
    settings = retrieval.RetrievalSettings(**read(ARTIFACTS / "metrics.json")["selected_settings"])
    path = ARTIFACTS / "answers.json"
    results = read(path) if path.exists() else {}
    model = os.getenv("GEMINI_LITE_MODEL", "gemini-3.5-flash-lite")
    with open_store() as store:
        for case in cases:
            if case["id"] not in records:
                raise RuntimeError("Missing retrieval case: " + case["id"])
            for strategy in ["keyword_original", "keyword", "hybrid"]:
                key = case["id"] + ":" + strategy
                current = ORIGINAL if strategy == "keyword_original" else settings
                evidence = ranked(records[case["id"]], current, strategy)
                if (
                    key in results
                    and results[key]["evidence_ids"] == [r["chunk_id"] for r in evidence]
                    and results[key]["model"] == model
                    and results[key].get("prompt_version") == PROMPT_VERSION
                ):
                    claims, withheld = validate_answer(
                        DraftAnswer.model_validate(results[key]["draft"]), evidence
                    )
                    results[key].update(claims=claims, withheld=withheld)
                    write(path, results)
                    continue
                started = time.perf_counter()
                draft, usage = generate(store, case["question"], evidence, model)
                claims, withheld = validate_answer(draft, evidence)
                results[key] = {
                    "model": model,
                    "prompt_version": PROMPT_VERSION,
                    "draft": draft.model_dump(),
                    "claims": claims,
                    "withheld": withheld,
                    "usage": usage,
                    "generation_ms": round((time.perf_counter() - started) * 1000, 2),
                    "evidence_ids": [r["chunk_id"] for r in evidence],
                }
                write(path, results)
                print(key, "claims", len(claims), "withheld", withheld, flush=True)
                time.sleep(8)  # Respect shared project generation quotas; resume is cached locally.


def latency(cases):
    settings = retrieval.RetrievalSettings(**read(ARTIFACTS / "metrics.json")["selected_settings"])
    measurements = []
    with open_store() as store:
        for repeat in range(3):
            for case in cases:
                for method in ["keyword", "hybrid"] if repeat % 2 == 0 else ["hybrid", "keyword"]:
                    result = retrieval.retrieve_with_diagnostics(
                        store,
                        case["symbol"],
                        case["question"],
                        strategy=method,
                        settings=settings,
                        **case["filters"],
                    )
                    if method == "hybrid" and (
                        result["mode"] != "hybrid"
                        or result["embedding_provider_calls"]
                        or not result["query_embedding_cached"]
                    ):
                        raise RuntimeError(
                            "Latency stage requires existing query embeddings and live hybrid retrieval."
                        )
                    measurements.append(
                        {
                            "case": case["id"],
                            "method": method,
                            "repeat": repeat,
                            "latency_ms": result["latency_ms"],
                        }
                    )
    report = {
        "settings": asdict(settings),
        "measurements": measurements,
        "median_ms": {
            method: round(
                statistics.median(r["latency_ms"] for r in measurements if r["method"] == method), 2
            )
            for method in ["keyword", "hybrid"]
        },
    }
    write(ARTIFACTS / "latency-selected.json", report)
    print(json.dumps(report["median_ms"]))


def main():
    load_local_env()
    os.environ["FINN_ENABLE_SEMANTIC_SEARCH"] = (
        "true"  # This process only; never changes deployment.
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["collect", "tune", "answers", "latency"])
    parser.add_argument("--symbols", nargs="*")
    args = parser.parse_args()
    cases = read(CASES)["cases"]
    if args.symbols:
        cases = [c for c in cases if c["symbol"] in args.symbols]
    if args.stage == "collect":
        collect(cases, args.symbols)
    elif args.stage == "tune":
        tune(cases)
    elif args.stage == "answers":
        answers(cases)
    else:
        latency(cases)


if __name__ == "__main__":
    main()
