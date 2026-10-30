"""Explainable filing priorities and real portfolio sync; no generated news or prices."""

from __future__ import annotations

import argparse
import hashlib
import os
import re

from bs4 import BeautifulSoup

from finn.config import load_local_env
from finn.corpus import now
from finn.jobs import safe_error
from finn.sources import announcement_feed, price_probe, public_client
from finn.store import open_store


def classify_filing(description: str) -> tuple[str, int, str]:
    text = description.lower()
    if re.search(r"newspaper|publication of.*results|published.*newspaper", text):
        return (
            "publication",
            0,
            "Publication notice; the actual results filing carries the financial detail.",
        )
    if re.search(
        r"esop|compliance certificate|demateriali[sz]ation|trading window|loss of share certificate|duplicate.*share certificate|investor grievance",
        text,
    ):
        return "routine", 0, "Routine disclosure; available here if you need the original."
    if "auditor" in text and "mandatory" in text and "rotation" in text:
        return (
            "routine",
            0,
            "Scheduled auditor rotation; expand to inspect the governance disclosure.",
        )
    if re.search(r"board meeting.*intimat|intimat.*board meeting|notice.*board meeting", text):
        return "meeting_notice", 1, "A scheduled board meeting; this is not the results themselves."
    if re.search(r"financial results|quarterly results|audited results|unaudited results", text):
        return (
            "results",
            3,
            "New results may change the financial picture. Review the original filing.",
        )
    if re.search(r"acquisition|merger|demerger|joint venture|scheme of arrangement", text):
        return (
            "m_and_a",
            3,
            "A potential change in the business or ownership structure deserves review.",
        )
    if re.search(r"resignation|appointment|cessation|retirement", text) and re.search(
        r"director|chief|ceo|cfo|management|officer", text
    ):
        return (
            "management_change",
            3,
            "Leadership changes can affect execution and oversight. Check the role and effective date.",
        )
    if re.search(
        r"litigation|penalt|regulatory order|insolvency|nclt|nclat|fine imposed|tax demand", text
    ):
        return (
            "litigation",
            3,
            "Review the scope and potential exposure in the original disclosure.",
        )
    if "rating" in text:
        return (
            "credit_rating",
            3 if "downgrad" in text else 1,
            "A rating change can affect funding risk; distinguish a downgrade from a reaffirmation.",
        )
    if (
        re.search(r"schedule|invitation|intimation", text)
        and re.search(r"(?:earnings|conference|analyst|investor).*(?:call|meet|discussion)", text)
        and not re.search(r"transcript|recording", text)
    ):
        return (
            "investor_meeting",
            0,
            "Scheduled discussion; management commentary is not established by the notice alone.",
        )
    if re.search(r"transcript|earnings call|conference call|analyst.*call", text):
        return (
            "earnings_call",
            1,
            "Management commentary is available for further company research."
            if re.search(r"transcript|recording", text)
            else "Call-related disclosure; inspect whether it is a notice, recording or transcript.",
        )
    if re.search(r"investor.*meet|analyst.*meet|investor conference", text):
        return (
            "investor_meeting",
            0,
            "Meeting notice; no new business information is established by the notice alone.",
        )
    if re.search(
        r"rights issue|qip|preferential allotment|fund rais|buyback|commercial paper", text
    ):
        return "capital", 2, "Review the terms and potential effect on capital or funding."
    if re.search(r"dividend|bonus|stock split|sub-division", text):
        return "corporate_action", 2, "Check the terms, record date, and eligibility in the filing."
    if re.search(
        r"capex|capacity expansion|new plant|order win|awarding of order|commercial operation|commissioning",
        text,
    ) or ("fda" in text and "approv" in text):
        return (
            "business_update",
            2,
            "A business development worth assessing in the context of the company.",
        )
    if re.search(r"shareholding pattern|postal ballot|annual general meeting|agm|egm", text):
        return "routine", 0, "Periodic governance disclosure; expand to inspect the original."
    return (
        "unclassified",
        2,
        "This disclosure has not been reliably classified. It remains visible for your review.",
    )


def sync_start(store, kind: str, origin: str = "local_manual") -> dict:
    old = store.rows("finn_sync_status", id="eq." + kind, limit=1)
    record = {
        "id": kind,
        "state": "running",
        "started_at": now(),
        "finished_at": None,
        "last_success_at": old[0]["last_success_at"] if old else None,
        "captured_since": old[0]["captured_since"] if old else None,
        "error": None,
        "details": execution_details(origin),
    }
    store.upsert("finn_sync_status", [record])
    return record


def execution_details(origin: str) -> dict:
    return {
        "execution_origin": origin,
        "automation_verified": origin in ["supabase_cron", "github_actions"],
    }


def sync_filings(store, companies: list[dict], *, origin: str = "local_manual") -> dict:
    record = sync_start(store, "filings", origin)
    try:
        with public_client() as client:
            feed = announcement_feed(client)
        norm = lambda text: re.sub(r"[^a-z0-9]", "", text.lower())
        directory = {norm(company["name"]): company for company in companies}
        filings = []
        for item in feed["items"]:
            company = directory.get(norm(item["company"]))
            if not company or not item["source_url"].startswith("https://"):
                continue
            description = BeautifulSoup(item["description"], "html.parser").get_text(
                " ", strip=True
            )
            category, priority, reason = classify_filing(description)
            title = (
                description.split("|SUBJECT:")[-1].strip()
                if "|SUBJECT:" in description
                else description
            )
            fingerprint = hashlib.sha256(
                f"{company['symbol']}|{item['source_url']}|{item['published_at']}|{description}".encode()
            ).hexdigest()
            filings.append(
                {
                    "id": fingerprint,
                    "symbol": company["symbol"],
                    "company_name": company["name"],
                    "title": title[:300],
                    "description": description,
                    "source_url": item["source_url"],
                    "published_at": item["published_at"],
                    "category": category,
                    "priority": priority,
                    "review_reason": reason,
                    "last_seen_at": now(),
                }
            )
        if filings:
            store.upsert("finn_filings", filings)
        errors, warnings = feed.get("parse_errors", []), feed.get("warnings", [])
        issues = warnings + (
            ["Some feed items had unrecognised timestamps and were excluded."] if errors else []
        )
        completed = {
            "state": "partial" if issues else "completed",
            "finished_at": now(),
            "last_success_at": now(),
            "captured_since": record["captured_since"] or record["started_at"],
            "error": " ".join(issues) if issues else None,
            "details": {
                **execution_details(origin),
                "portfolio_companies": len(companies),
                "feed_items": len(feed["items"]),
                "portfolio_filings": len(filings),
                "invalid_timestamps": len(errors),
                "coverage": "Recent NSE RSS plus filings captured since monitoring started. Earlier history may be incomplete.",
            },
        }
        store.patch("finn_sync_status", completed, id="eq.filings")
        return completed
    except Exception as exc:
        store.patch(
            "finn_sync_status",
            {"state": "failed", "finished_at": now(), "error": safe_error(exc)},
            id="eq.filings",
        )
        raise


def sync_prices(store, companies: list[dict], *, origin: str = "local_manual") -> dict:
    sync_start(store, "prices", origin)
    failed = []
    for company in companies:
        attempted = now()
        old = store.rows("finn_price_snapshots", symbol="eq." + company["symbol"], limit=1)
        try:
            data = price_probe(company)
            previous_data = old[0].get("data") if old else None
            if previous_data and data["last_session"] < previous_data["last_session"]:
                raise ValueError(
                    "The provider returned an older trading session. The newer saved session was retained."
                )
            store.upsert(
                "finn_price_snapshots",
                [
                    {
                        "symbol": company["symbol"],
                        "data": data,
                        "error": None,
                        "last_attempt_at": attempted,
                        "last_success_at": now(),
                    }
                ],
                conflict="symbol",
            )
            print(f"EOD fetched: {company['symbol']}", flush=True)
        except Exception as exc:
            failed.append(company["symbol"])
            # A prior price may remain visible, but always with a failed-refresh marker
            # and the original last_success/session dates. No silent substitution.
            values = {
                "symbol": company["symbol"],
                "last_attempt_at": attempted,
                "error": safe_error(exc),
                "data": old[0]["data"] if old else None,
                "last_success_at": old[0]["last_success_at"] if old else None,
            }
            store.upsert("finn_price_snapshots", [values], conflict="symbol")
            print(f"EOD failed: {company['symbol']}", flush=True)
    record = {
        "state": "completed"
        if not failed
        else "partial"
        if len(failed) < len(companies)
        else "failed",
        "finished_at": now(),
        "error": None if not failed else "Some portfolio prices could not be refreshed.",
        "details": {
            **execution_details(origin),
            "portfolio_companies": len(companies),
            "updated": len(companies) - len(failed),
            "failed_symbols": failed,
        },
    }
    if not failed:
        record["last_success_at"] = now()
    store.patch("finn_sync_status", record, id="eq.prices")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["all", "filings", "prices"], default="all")
    args = parser.parse_args()
    load_local_env()
    origin = os.getenv("FINN_SYNC_ORIGIN", "local_manual")
    with open_store() as store:
        companies = store.rows(
            "finn_companies", portfolio="eq.true", select="symbol,name,isin", order="symbol"
        )
        if len(companies) < 15:
            raise SystemExit("Verify the mock portfolio before starting portfolio sync.")
        failed = False
        if args.mode in ["all", "filings"]:
            try:
                result = sync_filings(store, companies, origin=origin)
                print("Filings:", result, flush=True)
                failed = failed or result["state"] != "completed"
            except Exception as exc:
                failed = True
                print("Filings failed:", safe_error(exc), flush=True)
        if args.mode in ["all", "prices"]:
            result = sync_prices(store, companies, origin=origin)
            print("Prices:", result, flush=True)
            failed = failed or result["state"] != "completed"
        if failed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
