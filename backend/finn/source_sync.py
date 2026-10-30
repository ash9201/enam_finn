"""Authenticated, leased source refresh on the existing serial API worker."""

from __future__ import annotations

from datetime import datetime, timedelta

from finn import jobs
from finn.briefing import sync_filings, sync_prices
from finn.corpus import now
from finn.store import open_store
from finn.sources import IST


def scheduled_mode(store, requested: str, trigger: str, *, current_time=None) -> str:
    """An announcement tick can recover a missed/partial EOD run after its due time.

    Weekend/holiday reads preserve the source's actual last session. The cutoff is a
    refresh deadline, not an assertion that the exchange traded on that date.
    """
    if requested != "filings" or trigger != "cron":
        return requested
    current_time = (current_time or datetime.now(IST)).astimezone(IST)
    cutoff = current_time.replace(hour=18, minute=15, second=0, microsecond=0)
    if current_time < cutoff:
        cutoff -= timedelta(days=1)
    while cutoff.weekday() >= 5:
        cutoff -= timedelta(days=1)
    rows = store.rows("finn_sync_status", id="eq.prices", limit=1)
    try:
        refreshed = datetime.fromisoformat(rows[0]["last_success_at"].replace("Z", "+00:00"))
        if rows[0]["state"] == "completed" and refreshed >= cutoff:
            return requested
    except (IndexError, KeyError, TypeError, ValueError):
        pass
    return "all"


def run_sync(token: str, mode: str, origin: str):
    with open_store() as store:
        # A restarted/expired worker must not take ownership of a later request.
        current = store.rows("finn_source_sync_job", id="eq.1", token="eq." + token)
        if not current or current[0]["state"] != "queued":
            return
        filters = {"id": "eq.1", "token": "eq." + token}
        store.patch("finn_source_sync_job", {"state": "running", "updated_at": now()}, **filters)
        results = {}
        try:
            companies = store.rows(
                "finn_companies", portfolio="eq.true", select="symbol,name,isin", order="symbol"
            )
            if len(companies) < 15:
                raise ValueError("Verify the mock portfolio before starting source sync.")
            for kind, sync in [("filings", sync_filings), ("prices", sync_prices)]:
                if mode not in ["all", kind]:
                    continue
                try:
                    results[kind] = sync(store, companies, origin=origin)
                except Exception as exc:
                    # Failure of one source must not suppress the other source.
                    results[kind] = {"state": "failed", "error": jobs.safe_error(exc)}
                    store.patch(
                        "finn_sync_status",
                        {
                            "state": "failed",
                            "finished_at": now(),
                            "error": jobs.safe_error(exc),
                        },
                        id="eq." + kind,
                    )
                store.patch(
                    "finn_source_sync_job", {"result": results, "updated_at": now()}, **filters
                )
            states = [item["state"] for item in results.values()]
            state = (
                "completed"
                if all(s == "completed" for s in states)
                else ("failed" if all(s == "failed" for s in states) else "partial")
            )
            store.patch(
                "finn_source_sync_job",
                {"state": state, "result": results, "finished_at": now(), "updated_at": now()},
                **filters,
            )
        except Exception as exc:
            store.patch(
                "finn_source_sync_job",
                {
                    "state": "failed",
                    "error": jobs.safe_error(exc),
                    "finished_at": now(),
                    "updated_at": now(),
                },
                **filters,
            )
