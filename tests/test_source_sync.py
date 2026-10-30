from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from finn import api, source_sync
from finn.main import app


class SyncStore:
    def __init__(self, *, acquired=True, active=False):
        self.acquired = acquired
        self.active = active
        self.patches = []
        self.rpcs = []

    def rows(self, table, **filters):
        if table == "finn_research_jobs":
            return [{"id": "busy"}] if self.active else []
        if table == "finn_source_sync_job":
            return [{"state": "queued"}]
        return [{"symbol": str(i)} for i in range(15)]

    def rpc(self, name, values):
        self.rpcs.append((name, values))
        return self.acquired

    def patch(self, table, values, **filters):
        self.patches.append((table, values, filters))


def install_store(monkeypatch, store):
    @contextmanager
    def open_store():
        yield store

    monkeypatch.setattr(api, "open_store", open_store)
    monkeypatch.setattr(source_sync, "open_store", open_store)
    monkeypatch.setattr(api.jobs, "expire_stale_jobs", lambda store: None)
    monkeypatch.setattr(
        api, "supabase_configuration", lambda: ("url", "test-server-secret", "public")
    )


def test_unauthenticated_sync_cannot_read_or_start_work(monkeypatch):
    install_store(monkeypatch, SyncStore())
    with TestClient(app) as client:
        for method in [client.get, client.post]:
            body = {"json": {}} if method.__name__ == "post" else {}
            assert method("/internal/source-sync", **body).status_code == 403
            assert (
                method(
                    "/internal/source-sync", headers={"X-Finn-Sync-Key": "public"}, **body
                ).status_code
                == 403
            )


@pytest.mark.parametrize("active,acquired", [(True, True), (False, False)])
def test_busy_research_or_existing_lease_does_not_queue_duplicate_sync(
    monkeypatch, active, acquired
):
    store = SyncStore(active=active, acquired=acquired)
    install_store(monkeypatch, store)
    monkeypatch.setattr(
        api.jobs.executor, "submit", lambda *args: pytest.fail("Duplicate worker submitted")
    )
    with TestClient(app) as client:
        response = client.post(
            "/internal/source-sync",
            json={"mode": "all"},
            headers={"X-Finn-Sync-Key": "test-server-secret"},
        )
    assert response.status_code == 409
    assert len(store.rpcs) == (0 if active else 1)


def test_accepted_request_is_queued_and_uses_shared_executor(monkeypatch):
    store = SyncStore()
    install_store(monkeypatch, store)
    submitted = []
    monkeypatch.setattr(api.jobs.executor, "submit", lambda *args: submitted.append(args))
    with TestClient(app) as client:
        response = client.post(
            "/internal/source-sync",
            json={"mode": "filings", "trigger": "cron"},
            headers={"X-Finn-Sync-Key": "test-server-secret"},
        )
    assert response.status_code == 202
    assert response.json()["state"] == "queued"
    assert submitted == [
        (source_sync.run_sync, response.json()["job_id"], "filings", "supabase_cron")
    ]
    assert store.rpcs[0][1]["p_origin"] == "supabase_cron"


def test_source_failure_still_runs_prices_and_cannot_become_completed(monkeypatch):
    store = SyncStore()
    install_store(monkeypatch, store)

    def filings(*args, **kwargs):
        raise RuntimeError("Source blocked")

    price_calls = []
    monkeypatch.setattr(source_sync, "sync_filings", filings)
    monkeypatch.setattr(
        source_sync,
        "sync_prices",
        lambda *args, **kwargs: (
            price_calls.append(kwargs) or {"state": "completed", "details": {"updated": 15}}
        ),
    )
    source_sync.run_sync("request-token", "all", "supabase_cron")
    assert price_calls == [{"origin": "supabase_cron"}]
    _, final, filters = store.patches[-1]
    assert final["state"] == "partial"
    assert final["result"]["filings"]["state"] == "failed"
    assert filters["token"] == "eq.request-token"
    assert any(
        table == "finn_sync_status" and values["state"] == "failed"
        for table, values, _ in store.patches
    )
