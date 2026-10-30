"""Run private, repeatable Milestone 0 checks. Does not serve or seed investor data.

python -m finn.feasibility --symbol INFY [--check-embeddings] [--only infrastructure]
Outputs contain no API keys. Actual source artifacts stay in ignored artifacts/.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import time
import uuid

import httpx

from finn.config import ROOT, load_local_env
from finn.documents import extract_document
from finn.services import (
    MissingConfiguration,
    probe_database,
    probe_embeddings,
    probe_model,
    probe_storage,
)
from finn.sources import (
    announcement_probe,
    discover_documents,
    fetch_pdf,
    price_probe,
    public_client,
    resolve_company,
)


class Runner:
    def __init__(self, output: Path, symbol: str):
        self.output = output
        self.output.mkdir(parents=True, exist_ok=True)
        self.report = {
            "run_id": str(uuid.uuid4()),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "milestone": 0,
            "checks": [],
            "gate": "not_verified",
            "financial_comparisons_enabled": False,
        }

    def check(self, name, function, *, required=True):
        started = time.monotonic()
        print(f"[checking] {name}", flush=True)
        entry = {
            "name": name,
            "required": required,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        result = None
        try:
            result = function()
            entry.update(status="passed", evidence=result)
        except MissingConfiguration as exc:
            entry.update(status="blocked", reason=str(exc))
        except Exception as exc:
            # Exceptions are scrubbed before either local console or report serialization.
            reason = str(exc)[:700]
            for key, value in os.environ.items():
                if any(word in key for word in ["KEY", "TOKEN", "PASSWORD"]) and len(value) > 8:
                    reason = reason.replace(value, "[REDACTED]")
            entry.update(status="failed", error_type=type(exc).__name__, reason=reason)
        entry["duration_seconds"] = round(time.monotonic() - started, 2)
        self.report["checks"].append(entry)
        self.save()
        print(
            f"[{entry['status']}] {name}" + (f": {entry['reason']}" if entry.get("reason") else ""),
            flush=True,
        )
        return result

    def save(self):
        (self.output / "feasibility.json").write_text(
            json.dumps(self.report, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def finish(self):
        required = [check for check in self.report["checks"] if check["required"]]
        self.report["gate"] = (
            "passed"
            if required and all(check["status"] == "passed" for check in required)
            else "not_verified"
        )
        self.report["finished_at"] = datetime.now(timezone.utc).isoformat()
        self.save()
        lines = [
            "# Milestone 0 feasibility report",
            "",
            f"Checked at: {self.report['finished_at']}",
            f"Company: {self.report['symbol']}",
            f"Gate: **{self.report['gate']}**",
            "",
            "| Check | Result | Notes |",
            "| --- | --- | --- |",
        ]
        for check in self.report["checks"]:
            note = (
                check.get("reason", "Live probe passed; inspect JSON for evidence.")
                .replace("|", "/")
                .replace("\n", " ")
            )
            lines.append(f"| {check['name']} | {check['status']} | {note} |")
        lines += [
            "",
            "Table extraction creates unvalidated candidates. Financial comparisons remain disabled.",
            "No cached or fabricated data replaces a failed live request.",
            "Later milestones remain gated until the external dependencies and deployment are verified.",
        ]
        (self.output / "feasibility.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Report: {self.output / 'feasibility.md'}", flush=True)
        return 0 if self.report["gate"] == "passed" else 1


def deployment_probe(kind: str) -> dict:
    url = os.getenv("FINN_DEPLOYED_" + kind.upper() + "_URL", "").rstrip("/")
    if not url:
        raise MissingConfiguration(
            f"FINN_DEPLOYED_{kind.upper()}_URL is unset; no deployed service has been assumed."
        )
    if not url.startswith("https://"):
        raise ValueError("A deployed service must have an HTTPS URL.")
    with httpx.Client(timeout=100) as client:
        started = time.monotonic()
        response = client.get(url + ("/health/live" if kind == "api" else "/"))
        response.raise_for_status()
        elapsed = round(time.monotonic() - started, 2)
        if kind == "api" and response.json().get("service") != "finn-api":
            raise ValueError("Deployment did not return the expected FINN API health response.")
        if kind == "web" and "FINN" not in response.text:
            raise ValueError("Deployment did not return the expected FINN HTML shell.")
    return {
        "url": url,
        "http_status": response.status_code,
        "elapsed_seconds": elapsed,
        "cold_start_note": "Cold-start timing requires a separate request after at least 15 minutes idle.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="INFY")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "milestone-0")
    parser.add_argument("--check-embeddings", action="store_true")
    parser.add_argument(
        "--only", choices=["all", "sources", "models", "infrastructure"], default="all"
    )
    args = parser.parse_args()
    load_local_env()
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    runner = Runner(args.output, args.symbol.upper())
    extracted, primary_pdfs = [], []
    if args.only in ["all", "sources"]:
        with public_client() as client:
            company = runner.check(
                "nse_company_directory", lambda: resolve_company(client, args.symbol)
            )
            if company:
                runner.check("nse_announcements", lambda: announcement_probe(client, company))
                runner.check("yahoo_completed_eod", lambda: price_probe(company))
                discovery = runner.check(
                    "generic_document_discovery", lambda: discover_documents(client, company)
                )
                if discovery:
                    for kind in ["annual_report", "transcript"]:
                        document = discovery["documents"][kind][0]

                        def extract(kind=kind, document=document):
                            data, final_url = fetch_pdf(client, document["source_url"])
                            metadata = {
                                **document,
                                "final_url": final_url,
                                "company": company,
                                "fetched_at": datetime.now(timezone.utc).isoformat(),
                            }
                            result = extract_document(data, metadata)
                            path = args.output / f"{company['symbol']}-{kind}.json"
                            path.write_text(
                                json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
                            )
                            (args.output / f"{company['symbol']}-{kind}.pdf").write_bytes(data)
                            extracted.append(result)
                            primary_pdfs.append(data)
                            return {
                                key: result[key]
                                for key in [
                                    "source_url",
                                    "final_url",
                                    "discovery_url",
                                    "discovery_label",
                                    "published_at",
                                    "reporting_period",
                                    "sha256",
                                    "bytes",
                                    "fetched_at",
                                    "page_count",
                                    "table_pages_checked",
                                    "table_coverage",
                                    "table_extraction_warnings",
                                ]
                            } | {
                                "extracted_characters": sum(
                                    len(page["text"]) for page in result["pages"]
                                ),
                                "table_candidates": len(result["tables"]),
                                "artifact": str(path.relative_to(ROOT))
                                if path.is_relative_to(ROOT)
                                else path.name,
                                "financial_comparisons_enabled": False,
                            }

                        runner.check(f"primary_{kind}_extraction", extract)
            else:
                runner.check(
                    "one_company_sources",
                    lambda: (_ for _ in ()).throw(
                        MissingConfiguration(
                            "Company resolution failed; dependent sources were not silently substituted."
                        )
                    ),
                )
    if args.only in ["all", "models"]:
        # The source excerpt is optional for an isolated connectivity rerun; the full run
        # validates exact quoting from the actually downloaded transcript.
        transcript = next((doc for doc in extracted if doc["kind"] == "transcript"), None)
        excerpt = (
            next(
                (
                    " ".join(page["text"].split())[:350]
                    for page in transcript["pages"]
                    if len(page["text"].strip()) > 350
                ),
                None,
            )
            if transcript
            else None
        )
        runner.check(
            "gemini_flash_lite",
            lambda: probe_model(
                os.getenv("GEMINI_LITE_MODEL", "gemini-3.5-flash-lite"), quote_text=excerpt
            ),
        )
        runner.check(
            "gemini_flash",
            lambda: probe_model(os.getenv("GEMINI_REASONING_MODEL", "gemini-3.8-flash")),
        )
        if args.check_embeddings:
            runner.check("gemini_embeddings_optional", probe_embeddings, required=False)
    if args.only in ["all", "infrastructure"]:
        runner.check("supabase_database_and_policies", probe_database)
        if not primary_pdfs:
            pdf = next(args.output.glob(f"{args.symbol.upper()}-*.pdf"), None)
            if pdf is None:
                # An explicit infrastructure-only recheck can use a previously fetched
                # primary PDF. This is a storage transport test, not a fresh source fetch.
                pdf = next(
                    (ROOT / "artifacts" / "milestone-0").glob(f"{args.symbol.upper()}-*.pdf"), None
                )
            if pdf:
                primary_pdfs.append(pdf.read_bytes())
        if primary_pdfs:
            runner.check("supabase_private_storage", lambda: probe_storage(primary_pdfs[-1]))
        else:
            runner.check(
                "supabase_private_storage",
                lambda: (_ for _ in ()).throw(
                    MissingConfiguration(
                        "Fetch a real source PDF before the storage round-trip check."
                    )
                ),
            )
        runner.check("deployed_api", lambda: deployment_probe("api"))
        runner.check("deployed_frontend", lambda: deployment_probe("web"))
    if args.only != "all":
        # A partial run is useful evidence, but cannot open the overall milestone gate.
        runner.check(
            "complete_milestone_run",
            lambda: (_ for _ in ()).throw(
                MissingConfiguration(
                    "This was a partial probe run. Run the full suite before opening the milestone gate."
                )
            ),
        )
    return runner.finish()


if __name__ == "__main__":
    raise SystemExit(main())
