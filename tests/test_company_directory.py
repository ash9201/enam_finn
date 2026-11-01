import copy
import json
from datetime import UTC, datetime

import httpx
import pytest

from finn import company_directory as directory
from finn.sources import resolve_company


@pytest.fixture(autouse=True)
def clear_directory_memory():
    directory._cache.clear()
    yield
    directory._cache.clear()


def capture():
    return json.loads(directory.SNAPSHOT.read_text(encoding="utf-8"))


class ReferenceStore:
    directory_cache_key = "test-project"

    def __init__(self, snapshot=None, known=None):
        self.objects = {directory.REFERENCE_PATH: snapshot} if snapshot else {}
        self.known = known

    def rows(self, table, **kwargs):
        return [self.known] if self.known else []

    def get_reference_snapshot(self, path):
        return self.objects.get(path)

    def put_reference_snapshot(self, path, value):
        self.objects[path] = copy.deepcopy(value)


def test_watchlist_and_unprepared_companies_resolve_without_live_nse_even_after_restart():
    calls = []
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(403))
    ) as client:
        for symbol in ["INFY", "M&M", "CCL", "HDFCBANK", "NTPC", "TCS", "JINDALSTEL"]:
            row = resolve_company(client, symbol, store=ReferenceStore())
            assert row["symbol"] == symbol
            assert row["directory_checked_at"] and row["isin"].startswith("IN")
        directory._cache.clear()
        assert resolve_company(client, "infy.ns")["name"] == "Infosys Limited"
    assert calls == []


def test_persistent_capture_newer_than_bundle_survives_process_restart_and_storage_failure(
    monkeypatch,
):
    value = capture()
    value["checked_at"] = datetime.now(UTC).isoformat()
    # Use a real verified identity, not a fabricated issuer entry.
    store = ReferenceStore(value)
    assert directory.directory_snapshot(store)["checked_at"] == value["checked_at"]
    directory._cache.clear()
    assert directory.directory_snapshot(store)["checked_at"] == value["checked_at"]
    monkeypatch.setattr(directory.time, "monotonic", lambda: 10000000000)
    from finn.services import DependencyError

    monkeypatch.setattr(
        store,
        "get_reference_snapshot",
        lambda path: (_ for _ in ()).throw(DependencyError("unreachable")),
    )
    assert directory.directory_snapshot(store)["checked_at"] == value["checked_at"]


def test_403_refresh_preserves_persistent_snapshot_and_throttles_repeated_attempts():
    original = capture()
    store = ReferenceStore(original)
    calls = []
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(403))
    ) as client:
        with pytest.raises(ValueError, match="last-known-good snapshot retained"):
            directory.refresh_directory(store, client, force=True)
        assert store.objects[directory.REFERENCE_PATH] == original
        assert store.objects["company-directory-refresh.json"]["state"] == "failed"
        assert resolve_company(client, "INFY", store=store)["name"] == "Infosys Limited"
        assert directory.refresh_directory(store, client)["state"] == "already_attempted"
    assert len(calls) == 2


def test_bootstrap_persists_original_dated_capture_when_official_endpoints_fail():
    store = ReferenceStore()
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403))) as client:
        with pytest.raises(ValueError):
            directory.refresh_directory(store, client, force=True)
    assert store.objects[directory.REFERENCE_PATH] == capture()


def test_successful_refresh_is_validated_and_retains_aliases_only_for_matching_isins():
    previous = capture()
    csv = "SYMBOL,NAME OF COMPANY,ISIN NUMBER,SERIES\n" + "\n".join(
        f'{row["symbol"]},"{row["name"]}",{row["isin"]},EQ' for row in previous["companies"]
    )
    store = ReferenceStore(previous)
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=csv))
    ) as client:
        result = directory.refresh_directory(store, client, force=True)
    refreshed = store.objects[directory.REFERENCE_PATH]
    assert result["state"] == "refreshed"
    assert len(refreshed["companies"]) == len(previous["companies"])
    for row in refreshed["companies"]:
        assert row["aliases"] == next(
            old["aliases"] for old in previous["companies"] if old["isin"] == row["isin"]
        )


@pytest.mark.parametrize(
    "response",
    [
        "<html>Access denied</html>",
        "SYMBOL,NAME OF COMPANY,ISIN NUMBER\nINFY,Infosys,INE009A01021\n",
    ],
)
def test_invalid_or_truncated_csv_cannot_replace_last_known_good(response):
    previous = capture()
    store = ReferenceStore(previous)
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=response))
    ) as client:
        with pytest.raises(ValueError):
            directory.refresh_directory(store, client, force=True)
    assert store.objects[directory.REFERENCE_PATH] == previous


def test_legacy_verified_company_is_usable_without_inventing_directory_freshness():
    value = capture()
    real = next(row for row in value["companies"] if row["symbol"] == "INFY")
    value["companies"] = [row for row in value["companies"] if row["symbol"] != "INFY"]
    store = ReferenceStore(value, real)
    # Mark the test snapshot newer so this exercises the exact stored-identity path.
    value["checked_at"] = datetime.now(UTC).isoformat()
    row = directory.resolve_identity("INFY", store=store)
    assert row["identity_source"] == "previously_resolved_company"
    assert row["directory_checked_at"] is None


def test_exact_symbols_and_isin_conflicts_never_substitute_a_similarly_named_company():
    real = next(row for row in capture()["companies"] if row["symbol"] == "INFY")
    other = next(row for row in capture()["companies"] if row["symbol"] == "TCS")
    with pytest.raises(ValueError, match="differs from the stored company"):
        directory.resolve_identity(
            "INFY", store=ReferenceStore(known={**real, "isin": other["isin"]})
        )
    for value in ["JINDALSTEEL", "UNKNOWNISSUER", "Infosys Limited", "https://example.com"]:
        with pytest.raises(ValueError):
            directory.resolve_identity(value)


def test_persistent_or_prior_identity_does_not_require_the_bundled_file(monkeypatch, tmp_path):
    value = capture()
    real = next(row for row in value["companies"] if row["symbol"] == "INFY")
    monkeypatch.setattr(directory, "SNAPSHOT", tmp_path / "missing.json")
    assert directory.resolve_identity("INFY", store=ReferenceStore(value))["isin"] == real["isin"]
    directory._cache.clear()
    assert (
        directory.resolve_identity("INFY", store=ReferenceStore(known=real))["identity_source"]
        == "previously_resolved_company"
    )
    directory._cache.clear()
    with pytest.raises(ValueError, match="could not be verified"):
        directory.resolve_identity("UNKNOWNISSUER", store=ReferenceStore())


def test_internal_directory_status_is_operator_only_and_does_not_start_research(monkeypatch):
    from contextlib import nullcontext
    from fastapi.testclient import TestClient
    from finn import api
    from finn.main import app

    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test-operator")
    monkeypatch.setattr(api, "open_store", lambda: nullcontext(ReferenceStore()))
    with TestClient(app) as client:
        assert client.get("/internal/company-directory").status_code == 403
        result = client.get(
            "/internal/company-directory?symbol=INFY", headers={"x-finn-sync-key": "test-operator"}
        )
        assert result.status_code == 200
        assert result.json()["company"]["isin"] == "INE009A01021"
        assert result.json()["companies"] == len(capture()["companies"])
        result = client.get(
            "/internal/company-directory?symbol=UNKNOWNISSUER",
            headers={"x-finn-sync-key": "test-operator"},
        )
        assert result.status_code == 400 and "not found" in result.json()["detail"]


@pytest.mark.parametrize("pipeline", ["corpus", "financials"])
def test_refresh_pipeline_reaches_primary_discovery_without_a_live_directory(monkeypatch, pipeline):
    from finn import corpus, financials

    real = next(row for row in capture()["companies"] if row["symbol"] == "INFY")

    class Store(ReferenceStore):
        def rows(self, table, **kwargs):
            return (
                [{**real, "manifest": [], "source_checked_at": None}]
                if table == "finn_companies"
                else []
            )

        def upsert(self, *args, **kwargs):
            pass

    calls = []
    module = corpus if pipeline == "corpus" else financials
    monkeypatch.setattr(
        module,
        "public_client",
        lambda: httpx.Client(
            transport=httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(403))
        ),
    )

    def primary_discovery(client, company):
        assert company["symbol"] == "INFY" and company["isin"] == real["isin"]
        raise ValueError("primary document discovery reached")

    monkeypatch.setattr(
        module,
        "discover_documents" if pipeline == "corpus" else "discover_results",
        primary_discovery,
    )
    with pytest.raises(ValueError, match="primary document discovery reached"):
        if pipeline == "corpus":
            corpus.ensure_corpus(Store(), "INFY", refresh=True)
        else:
            financials.analyse_results(Store(), "INFY", refresh=True)
    assert calls == []
