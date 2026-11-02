import copy
from uuid import uuid4

import httpx
import pytest

from scripts import verify_submission as submission


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/research"),
        ("POST", "/rest/v1/finn_research_jobs"),
        ("PATCH", "/rest/v1/finn_documents"),
        ("DELETE", "/rest/v1/finn_research_cache"),
        ("POST", "/rest/v1/rpc/finn_reserve_embedding_request"),
        ("POST", "/storage/v1/object/pdfs/test"),
    ],
)
def test_submission_guard_blocks_all_mutations_and_quota_reservations(method, path):
    with pytest.raises(AssertionError, match="Read-only"):
        submission.readonly_request(httpx.Request(method, "https://store.example" + path))


def test_submission_guard_allows_only_reads_and_audited_select_rpcs():
    submission.readonly_request(
        httpx.Request("GET", "https://store.example/rest/v1/finn_documents")
    )
    submission.readonly_request(
        httpx.Request("POST", "https://store.example/rest/v1/rpc/finn_embedding_status")
    )


def test_report_skips_explicitly_fails_nonzero_and_never_echoes_http_exceptions(capsys):
    report = submission.Report()
    report.check(
        "temporary",
        lambda: (_ for _ in ()).throw(httpx.ReadTimeout("private-token-and-source-text")),
    )
    report.check(
        "optional", lambda: (_ for _ in ()).throw(submission.SkipCheck("No fixture available."))
    )
    assert report.finish() == 1
    text = capsys.readouterr().out
    assert "private-token" not in text and "SKIP" in text and "FAIL" in text


def mocked_api(monkeypatch, *, bad_index=False, bad_health=False):
    parent, cite, doc = [str(uuid4()) for _ in range(3)]
    citation = {
        "id": cite,
        "document_id": doc,
        "pdf_page": 7,
        "quote": "The company supplies software services.",
        "source_url": "https://issuer.example/report.pdf",
    }
    answer = {
        "id": parent,
        "symbol": "INFY",
        "question": "Explain the business.",
        "source_checked_at": "2026-11-01T00:00:00Z",
        "cache_created_at": "2026-11-01T00:00:00Z",
        "cached": True,
        "status": "answered",
        "claims": [{"statement": "Software services.", "citation": citation}],
    }
    seen = []

    def respond(request):
        seen.append((request.method, request.url.path))
        path = request.url.path
        if path == "/health/live":
            body = {
                "status": "bad" if bad_health else "ok",
                "service": "finn-api",
                "version": "0.2.0",
            }
        elif path == "/health/ready":
            body = {
                "dependencies_verified": False,
                "configuration": {
                    "gemini": True,
                    "supabase": True,
                    "public_cache": True,
                    "semantic_search_enabled": True,
                },
            }
        elif path == "/companies":
            body = {"companies": [{"symbol": "INFY", "name": "Infosys Limited"}]}
        elif path.endswith("/research"):
            body = answer
        elif path.endswith("/search-status"):
            body = {
                "symbol": "INFY",
                "checked_at": "2026-11-01",
                "state": "ready" if bad_index else "indexing",
                "index": {"ready": 1, "total": 3},
            }
        elif path.startswith("/research/"):
            if request.url.params["symbol"] != "INFY" or path.rsplit("/", 1)[-1] != cite:
                return httpx.Response(422, json={"detail": "Invalid reference."})
            body = {"research_id": parent, "symbol": "INFY", "citation": citation}
        else:
            raise AssertionError("Unexpected request")
        return httpx.Response(200, json=body)

    real_client = httpx.Client
    monkeypatch.setattr(
        submission.httpx,
        "Client",
        lambda **kw: real_client(transport=httpx.MockTransport(respond), **kw),
    )
    monkeypatch.setattr(submission, "supabase_configuration", lambda: ("", "", ""))
    monkeypatch.delenv("FINN_DEPLOYED_WEB_URL", raising=False)
    return seen


def test_live_submission_is_get_only_repeats_cached_reads_and_does_not_claim_semantic_execution(
    monkeypatch, capsys
):
    seen = mocked_api(monkeypatch)
    report = submission.Report()
    submission.live_checks(report, "https://api.example", ["INFY"], 2, public_only=True)
    assert report.finish() == 0
    assert all(method == "GET" for method, path in seen)
    assert seen.count(("GET", "/companies/INFY/research")) == 2
    text = capsys.readouterr().out
    assert "keyword fallback required" in text and "Deliberately not called" in text


@pytest.mark.parametrize("option", ["bad_index", "bad_health"])
def test_successful_http_with_incorrect_health_or_index_content_fails(monkeypatch, option):
    mocked_api(monkeypatch, **{option: True})
    report = submission.Report()
    submission.live_checks(report, "https://api.example", ["INFY"], 2, public_only=True)
    assert report.finish() == 1


def test_financial_sanity_rejects_mixed_bases_and_missing_values_as_zero():
    metric = {
        "id": "net_margin",
        "name": "Net profit margin",
        "status": "verified",
        "value": "10",
        "unit": "%",
        "basis": "consolidated",
        "period_end": "2026-03-31",
        "method": "calculated",
        "formula": "PAT / revenue * 100",
        "inputs": [{"basis": "standalone", "claim_index": 0}],
    }
    answer = {
        "question": "net profit margin",
        "claims": [],
        "financial_metrics": {"results": [metric]},
    }
    with pytest.raises(AssertionError, match="bases"):
        submission.financial_metadata(answer)
    invalid = copy.deepcopy(answer)
    invalid["financial_metrics"]["results"] = [
        {"id": "net_margin", "status": "unavailable", "reason": "Missing", "value": "0"}
    ]
    with pytest.raises(AssertionError, match="Missing metric"):
        submission.financial_metadata(invalid)


def test_private_page_policy_probe_uses_its_real_composite_key(monkeypatch):
    from finn import company_directory, services

    class Store:
        def rpc(self, name, values):
            return {"rls": {str(i): True for i in range(7)}}

        def rows(self, table, **kw):
            return [{"id": "private-cache-id"}] if kw.get("is_public") == "eq.false" else []

    snapshot = {
        "companies": [{"symbol": "INFY", "isin": "INE009A01021", "name": "Infosys Limited"}],
        "sources": ["https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"],
        "checked_at": "2026-11-01",
    }
    monkeypatch.setattr(company_directory, "directory_snapshot", lambda *a: snapshot)
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path.endswith("finn_document_pages"):
            assert request.url.params["select"] == "document_id"
        return (
            httpx.Response(200, json=[])
            if request.url.path.endswith("finn_research_cache")
            else httpx.Response(401, json={})
        )

    monkeypatch.setattr(
        services,
        "supabase_client",
        lambda key: httpx.Client(
            base_url="https://store.example/", transport=httpx.MockTransport(handler)
        ),
    )
    report = submission.Report()
    with httpx.Client() as client:
        submission.private_checks(
            report,
            Store(),
            client,
            lambda *a, **kw: {
                "companies": 2000,
                "sources": snapshot["sources"],
                "checked_at": snapshot["checked_at"],
            },
            ["INFY"],
            {},
            {},
            lambda *a: None,
            "public-key",
        )
    assert (
        next(row[0] for row in report.items if row[1] == "Live database access safeguards")
        == "PASS"
    )
    assert any(r.url.path.endswith("finn_document_pages") for r in seen)
