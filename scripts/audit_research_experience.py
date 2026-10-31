"""Read-only research audit. --sources downloads original quarterly PDFs, never calls an LLM."""

import argparse
import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from finn.config import load_local_env
from finn.financial_tables import extract_results_pdf
from finn.financials import (
    QUESTION,
    company_identity,
    discover_results,
    eligible_rows,
    primary_result_pdf,
)
from finn.sources import public_client, resolve_company
from finn.store import open_store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", action="store_true")
    args = parser.parse_args()
    load_local_env()
    output = Path("artifacts/experience-audit")
    output.mkdir(parents=True, exist_ok=True)
    with open_store() as store:
        companies = store.rows("finn_companies", order="symbol")
        jobs = store.rows("finn_research_jobs", order="created_at.desc", limit=1000)
        cache = store.rows(
            "finn_research_cache",
            select="id,symbol,question,result,is_public,created_at",
            order="created_at.desc",
            limit=1000,
        )
        (output / "baseline-private.json").write_text(
            json.dumps({"companies": companies, "jobs": jobs, "cache": cache}, indent=2),
            encoding="utf-8",
        )
        portfolio = [c for c in companies if c["portfolio"]]
        summary = []
        for c in portfolio:
            symbol = c["symbol"]
            latest = next(
                (j for j in jobs if j["symbol"] == symbol and j["question"] == QUESTION), {}
            )
            saved = next(
                (r["result"] for r in cache if r["symbol"] == symbol and r["question"] == QUESTION),
                {},
            )
            row = {
                "symbol": symbol,
                "corpus": c.get("coverage"),
                "financial_state": latest.get("state"),
                "error": latest.get("error"),
                "financial_status": saved.get("status"),
                "facts": len(saved.get("claims", [])),
                "seconds": round(
                    (
                        datetime.fromisoformat(latest["updated_at"])
                        - datetime.fromisoformat(latest["created_at"])
                    ).total_seconds(),
                    2,
                )
                if latest
                else None,
            }
            summary.append(row)
            print(json.dumps(row), flush=True)
        print("Job states", dict(Counter(j["state"] for j in jobs)), flush=True)
        (output / "baseline-summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
    if args.sources:
        with public_client() as client:
            for c in portfolio:
                symbol = c["symbol"]
                started = time.perf_counter()
                try:
                    company = resolve_company(client, symbol)
                    index, links = discover_results(client, company)
                    period, link = links[0]
                    source, data = primary_result_pdf(client, link)
                    metadata = {
                        "kind": "quarterly_results",
                        "source_url": source,
                        "discovery_url": index,
                        "discovery_label": period,
                        "reporting_period": period,
                    }
                    (output / (symbol + ".pdf")).write_bytes(data[0])
                    extracted = extract_results_pdf(data[0], metadata)
                    tables = extracted["tables"]
                    identity = company_identity(company["name"])
                    checked = [t for t in tables if identity in company_identity(t["header"])]
                    row = {
                        "symbol": symbol,
                        "period": period,
                        "source": metadata["source_url"],
                        "seconds": round(time.perf_counter() - started, 2),
                        "pages": extracted["page_count"],
                        "tables": len(tables),
                        "identity_tables": len(checked),
                        "metadata": [
                            {
                                "page": t["pdf_page"],
                                "basis": t["basis"],
                                "currency": t["currency"],
                                "unit": t["unit"],
                                "columns": t["columns"],
                                "rows": {
                                    m: [r["cells"][0] for r in eligible_rows(t, m)]
                                    for m in ["Revenue", "PBT", "PAT", "EBITDA"]
                                },
                            }
                            for t in tables
                        ],
                    }
                    (output / (symbol + "-native.json")).write_text(
                        json.dumps(extracted, indent=2), encoding="utf-8"
                    )
                    (output / (symbol + "-source.json")).write_text(
                        json.dumps({"company": company, "metadata": metadata}, indent=2),
                        encoding="utf-8",
                    )
                except Exception as exc:
                    row = {
                        "symbol": symbol,
                        "error": str(exc),
                        "seconds": round(time.perf_counter() - started, 2),
                    }
                (output / (symbol + "-audit.json")).write_text(
                    json.dumps(row, indent=2), encoding="utf-8"
                )
                print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
