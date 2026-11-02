"""Bounded, read-only pre-submission checks; never submits research or calls Gemini.

Default: local regression/build checks plus configured live API and optional private
reads. --local-only / --live-only separate the two. No source refresh or backfill.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from finn.config import load_local_env, supabase_configuration
from finn.documents import resolve_source_quote
from finn.store import Store
from scripts.check_frontend_secrets import configured_secrets, contains_secret

READ_RPCS = {
    "finn_research_security_status",
    "finn_embedding_status",
    "finn_embedding_budget",
    "finn_keyword_search_v2",
}


class SkipCheck(Exception):
    pass


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def readonly_request(request):
    """Fail closed before a network write; only audited SELECT-only RPCs are allowed."""
    if request.method == "GET":
        return
    if (
        request.method == "POST"
        and request.url.path.startswith("/rest/v1/rpc/")
        and request.url.path.rsplit("/", 1)[-1] in READ_RPCS
    ):
        return
    raise AssertionError("Read-only check blocked a mutation or unaudited RPC.")


class ReadOnlyStore(Store):
    def __init__(self, timeout):
        super().__init__()
        self.client.timeout = httpx.Timeout(timeout, connect=min(timeout, 10))
        self.client.event_hooks["request"].append(readonly_request)


class Report:
    def __init__(self):
        self.items = []

    def check(self, name, function):
        try:
            message = function() or "Verified."
            status = "PASS"
        except SkipCheck as exc:
            status, message = "SKIP", str(exc)
        except AssertionError as exc:
            status, message = "FAIL", str(exc) or "Validation failed."
        except Exception as exc:
            # HTTP exceptions can include private URLs; never echo arbitrary exception text.
            status, message = (
                "FAIL",
                f"{type(exc).__name__}; check service/configuration and rerun.",
            )
        self.items.append((status, name, message))
        print(f"{status:4} {name}: {message}", flush=True)
        return status

    def finish(self):
        counts = {
            state: sum(item[0] == state for item in self.items)
            for state in ["PASS", "FAIL", "SKIP"]
        }
        print(
            "Summary: "
            + ", ".join(f"{count} {state.lower()}" for state, count in counts.items())
            + ". Skipped checks remain unverified."
        )
        return int(counts["FAIL"] > 0)


def command(args, label, timeout=180):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    require(
        result.returncode == 0,
        label
        + " failed; run that command directly for local details (output suppressed to protect source text/configuration).",
    )
    match = re.search(r"\d+ passed", result.stdout)
    return match[0] if match else label + " passed."


def local_checks(report):
    tests = [
        "test_evidence_followup.py",
        "test_financial_results.py",
        "test_numerical_metrics.py",
        "test_hybrid.py",
        "test_company_directory.py",
        "test_research.py",
        "test_submission.py",
    ]
    report.check(
        "Local backend regressions",
        lambda: command(
            [sys.executable, "-m", "pytest", *[str(ROOT / "tests" / name) for name in tests]],
            "Relevant backend regressions",
        ),
    )

    def frontend():
        toolchain = ROOT / ".tools/toolchain.json"
        if toolchain.exists() and Path(json.loads(toolchain.read_text())["node"]).exists():
            runner = [sys.executable, str(ROOT / "scripts/npm.py")]
        elif shutil.which("npm"):
            runner = [shutil.which("npm"), "--prefix", str(ROOT / "frontend")]
        else:
            raise SkipCheck(
                "Node/npm unavailable; run npm run build and test:company-search from frontend."
            )
        result = command([*runner, "run", "build"], "Frontend production build")
        command(
            [*runner, "run", "test:company-search"], "Existing name/alias/ambiguous selection tests"
        )
        return result + " Name/alias/ambiguity tests passed."

    built = report.check("Frontend build and company selection", frontend)
    if built == "PASS":
        report.check(
            "Local frontend secret scan",
            lambda: command(
                [sys.executable, str(ROOT / "scripts/check_frontend_secrets.py")],
                "Existing credential scan",
            ),
        )


def valid_answer(answer, symbol):
    require(
        answer.get("symbol") == symbol,
        "Cached company identity differs from the requested company.",
    )
    require(
        answer.get("id") and answer.get("source_checked_at"),
        "Missing cached answer identity or original source timestamp.",
    )
    for claim in answer.get("claims", []):
        for citation in claim.get("citations") or [claim["citation"]]:
            require(
                citation.get("document_id")
                and citation.get("quote")
                and isinstance(citation.get("pdf_page"), int)
                and citation["pdf_page"] > 0,
                "A cached citation has incomplete document/passage/page provenance.",
            )
    if not answer.get("claims"):
        require(
            answer.get("status") in {"insufficient_evidence", "unavailable"}
            and (answer.get("limitations") or answer.get("assessment")),
            "Empty coverage is not explained.",
        )


def financial_metadata(answer):
    """Validate retained metadata, not new arithmetic or a new financial extractor."""
    claims = answer["claims"]
    results = answer.get("financial_results")
    if results:
        require(
            results.get("periods") and results.get("sources"),
            "Quarterly source/period metadata is missing.",
        )
        for basis, statement in results["bases"].items():
            require(
                basis in {"standalone", "consolidated"}
                and statement.get("unit")
                and statement.get("currency"),
                "Quarterly basis/units/currency is missing.",
            )
            for row in statement["rows"]:
                for period, figure in row["figures"].items():
                    citation = claims[figure["claim_index"]]["citation"]["financial_evidence"]
                    require(
                        citation["accounting_basis"] == basis
                        and citation["period_end"] == results["periods"][period]
                        and citation["unit"] == statement["unit"]
                        and citation["currency"] == statement["currency"],
                        "Financial figure provenance has incompatible period, basis or units.",
                    )
                if not row["figures"]:
                    require(
                        row.get("missing_reason"),
                        "Unavailable financial figure lacks an explanation.",
                    )
    metrics = answer.get("financial_metrics")
    if metrics:
        from finn.metric_registry import financial_intent
        from finn.metric_research import complete_numerical_answer

        require(
            complete_numerical_answer(financial_intent(answer["question"]), metrics["results"]),
            "Numerical intent is incomplete.",
        )
        for metric in metrics["results"]:
            if metric["status"] == "unavailable":
                require(
                    metric.get("reason") and metric.get("value") is None,
                    "Missing metric became a number or lost its explanation.",
                )
                continue
            require(
                Decimal(metric["value"]).is_finite()
                and metric.get("unit")
                and metric.get("basis")
                and metric.get("period_end"),
                "Verified metric has incomplete numerical metadata.",
            )
            if metric.get("method") == "calculated":
                require(
                    metric.get("formula") and metric.get("inputs"),
                    "Calculated value lost formula or inputs.",
                )
                for value in metric["inputs"]:
                    require(
                        value["basis"] == metric["basis"], "Calculated inputs mix accounting bases."
                    )
                    require(
                        value.get("claim_index") is not None or value.get("inputs"),
                        "A calculated input lost its source reference.",
                    )
    require(results or metrics, "No retained numerical result in this case.")


def live_checks(report, api_url, symbols, timeout, public_only=False):
    parsed = urlsplit(api_url)
    require(
        parsed.scheme in {"http", "https"}
        and parsed.hostname
        and not parsed.username
        and not parsed.password
        and not parsed.query,
        "Use a valid API URL without credentials/query parameters.",
    )
    prepared, profiles = {}, {}
    with httpx.Client(
        base_url=api_url.rstrip("/") + "/", timeout=httpx.Timeout(timeout, connect=min(timeout, 10))
    ) as client:

        def get(path, **kwargs):
            response = client.get(path, **kwargs)
            require(
                response.status_code == 200,
                f"HTTP {response.status_code} from a read-only API check; check deployment/data coverage.",
            )
            return response.json()

        def health():
            value = get("health/live")
            require(
                value.get("status") == "ok"
                and value.get("service") == "finn-api"
                and value.get("version"),
                "Unexpected liveness response.",
            )
            return "FINN API reachable; liveness content validated."

        if report.check("Live API liveness", health) != "PASS":
            report.check(
                "Dependent live checks",
                lambda: (_ for _ in ()).throw(
                    SkipCheck("API unreachable; no research/provider calls attempted.")
                ),
            )
            return

        def ready():
            value = get("health/ready")
            config = value.get("configuration", {})
            require(
                all(config.get(key) is True for key in ["gemini", "supabase", "public_cache"]),
                "Required backend configuration is missing.",
            )
            require(
                value.get("dependencies_verified") is False,
                "Unexpected readiness contract; configuration must not claim connectivity.",
            )
            return (
                "Required settings present; semantic flag="
                + str(config.get("semantic_search_enabled"))
                + ". Provider connectivity is not implied."
            )

        report.check("Live configuration", ready)

        def companies():
            values = get("companies").get("companies")
            require(
                isinstance(values, list)
                and values
                and all(v.get("symbol") and v.get("name") for v in values),
                "Watchlist identity records are missing.",
            )
            return f"{len(values)} watchlist identities read from backend storage."

        report.check("Live database-backed company reads", companies)
        for symbol in symbols:

            def cached(symbol=symbol):
                response = client.get(f"companies/{symbol}/research")
                if response.status_code == 404:
                    raise SkipCheck(
                        "No current published prepared answer; coverage is unavailable. No job was submitted."
                    )
                require(response.status_code == 200, "Prepared research read failed.")
                value = response.json()
                valid_answer(value, symbol)
                require(
                    value.get("cached") is True and value.get("cache_created_at"),
                    "Prepared API response lost cache provenance.",
                )
                repeated = get(f"companies/{symbol}/research")
                require(
                    all(
                        value.get(k) == repeated.get(k)
                        for k in ["id", "symbol", "source_checked_at", "cache_created_at", "claims"]
                    ),
                    "Unchanged cached reads changed answer identity/provenance.",
                )
                prepared[symbol] = value
                return "Identical cached GETs; original timestamps/citations preserved. No POST/job/backfill."

            report.check(symbol + " prepared research", cached)

            def index(symbol=symbol):
                value = get(f"companies/{symbol}/search-status")
                require(
                    value.get("symbol") == symbol and value.get("checked_at"),
                    "Invalid search status identity/timestamp.",
                )
                profiles[symbol] = value
                if value["state"] == "disabled":
                    return "Semantic retrieval disabled; keyword mode. No embedding request."
                counts = value.get("index")
                require(
                    counts and 0 <= counts["ready"] <= counts["total"],
                    "Search-index coverage is unknown or invalid.",
                )
                complete = counts["total"] > 0 and counts["ready"] == counts["total"]
                require(
                    (value["state"] == "ready") == complete,
                    "Reported hybrid readiness disagrees with actual index counts.",
                )
                return f"{counts['ready']}/{counts['total']} chunks; " + (
                    "hybrid eligible, not a live semantic query."
                    if complete
                    else "keyword fallback required."
                )

            report.check(symbol + " actual retrieval coverage", index)

        def verify_evidence(answer):
            if not answer.get("claims"):
                raise SkipCheck("Saved answer has no supported claims; no evidence invented.")
            claim = answer["claims"][0]
            citation = claim["citation"]
            path = f"research/{answer['id']}/evidence/{citation['id']}"
            params = {"symbol": answer["symbol"], "claim_index": 0}
            value = get(path, params=params)
            actual = value.get("citation", {})
            require(
                value.get("symbol") == answer["symbol"]
                and value.get("research_id") == answer["id"]
                and all(
                    actual.get(k) == citation.get(k) for k in ["id", "document_id", "pdf_page"]
                ),
                "Evidence belongs to a different company/document/page/answer.",
            )
            require(
                resolve_source_quote(citation["quote"], actual.get("quote", "")),
                "Stored source passage differs from the saved citation.",
            )
            wrong = client.get(path, params={**params, "symbol": "ZZINVALID"})
            invalid = client.get(f"research/{answer['id']}/evidence/{uuid4()}", params=params)
            require(
                wrong.status_code == 422 and invalid.status_code == 422,
                "Invalid company/citation was accepted.",
            )
            link = actual.get("document_url") or actual.get("source_url") or ""
            require(
                urlsplit(link).scheme == "https"
                and urlsplit(link).hostname
                and not urlsplit(link).username
                and not urlsplit(link).password
                and actual["pdf_page"] > 0,
                "Original PDF page link cannot be safely formed.",
            )
            return "Stored passage/company/document/page and rejection checks pass; external PDF availability was not probed."

        for symbol, answer in prepared.items():
            report.check(
                symbol + " evidence integrity", lambda answer=answer: verify_evidence(answer)
            )
        database_url, secret, public = supabase_configuration()
        if public_only or not database_url or not secret:
            report.check(
                "Private read-only checks",
                lambda: (_ for _ in ()).throw(
                    SkipCheck(
                        "Server credentials unavailable or --public-only selected; private cache/RLS/fallback remain unverified."
                    )
                ),
            )
        else:
            store = ReadOnlyStore(timeout)
            try:
                private_checks(
                    report, store, client, get, symbols, prepared, profiles, verify_evidence, public
                )
            finally:
                store.close()
        report.check(
            "Live Gemini generation/semantic ranking",
            lambda: (_ for _ in ()).throw(
                SkipCheck(
                    "Deliberately not called: preserves Gemini quota. Live flags/coverage and injected fallback are separate checks."
                )
            ),
        )

        def assets():
            web = os.getenv("FINN_DEPLOYED_WEB_URL", "")
            if not web:
                raise SkipCheck(
                    "FINN_DEPLOYED_WEB_URL not configured; only local assets can be checked."
                )
            response = client.get(web)
            require(response.status_code == 200, "Frontend is not reachable.")
            paths = re.findall(r'(?:src|href)=["\']([^"\']+\.(?:js|css))["\']', response.text)
            urls = {
                urljoin(web, path)
                for path in paths
                if urlsplit(urljoin(web, path)).netloc == urlsplit(web).netloc
            }
            require(urls and len(urls) <= 12, "Unexpected frontend asset manifest.")
            for url in urls:
                response = client.get(url)
                require(
                    response.status_code == 200
                    and not contains_secret(response.content, configured_secrets()),
                    "A deployed asset failed loading or the existing privileged-secret scan.",
                )
            return f"{len(urls)} deployed JS/CSS assets checked using the existing secret scanner."

        report.check("Deployed frontend assets", assets)


def private_checks(
    report, store, client, get, symbols, prepared, profiles, verify_evidence, public
):
    from finn import embeddings, retrieval
    from finn.company_directory import directory_snapshot, resolve_identity
    from finn.research import fast_cached_research

    def identities():
        _, secret, _ = supabase_configuration()
        snapshot = get("internal/company-directory", headers={"x-finn-sync-key": secret})
        require(
            snapshot.get("companies", 0) > 1000
            and snapshot.get("sources")
            and snapshot.get("checked_at"),
            "Persistent directory provenance is missing.",
        )
        directory = directory_snapshot(store)
        for symbol in symbols:
            resolved = resolve_identity(symbol, store=store)
            expected = next((r for r in directory["companies"] if r["symbol"] == symbol), None)
            require(
                expected
                and resolved["isin"] == expected["isin"]
                and resolved["name"] == expected["name"],
                "Canonical symbol/ISIN/name mismatch.",
            )
        try:
            resolve_identity("ZZINVALID", store=store)
        except ValueError:
            pass
        else:
            raise AssertionError("Unknown identity was substituted.")
        return "Verified snapshot/ISINs and invalid-symbol rejection; no live NSE fetch or directory refresh."

    report.check("Persistent company identity fallback", identities)

    def security():
        value = store.rpc("finn_research_security_status", {})
        require(
            len(value.get("rls", {})) == 7
            and all(value["rls"].values())
            and not any(
                value.get(k)
                for k in ["anon_bypasses_rls", "anon_private_select", "anon_cache_write"]
            ),
            "Research access audit failed.",
        )
        if not public:
            raise SkipCheck(
                "Server RLS audit passed; publishable key missing for anonymous denial checks."
            )
        from finn.services import supabase_client

        with supabase_client(public) as anon:
            anon.timeout = httpx.Timeout(client.timeout.read)
            for table in [
                "finn_documents",
                "finn_document_pages",
                "finn_research_chunks",
                "finn_research_jobs",
            ]:
                response = anon.get(
                    "rest/v1/" + table,
                    params={
                        "select": "document_id" if table == "finn_document_pages" else "id",
                        "limit": 1,
                    },
                )
                require(
                    response.status_code in {200, 401, 403},
                    "Anonymous read probe returned an unexpected HTTP status; check its schema/query before assessing access.",
                )
                require(
                    response.status_code in {401, 403}
                    or response.status_code == 200
                    and response.json() == [],
                    "Anonymous access exposed a private research table.",
                )
            private = store.rows("finn_research_cache", is_public="eq.false", select="id", limit=1)
            if not private:
                raise SkipCheck(
                    "Private-table audit passed, but no unpublished cache row exists to test its hiding."
                )
            response = anon.get(
                "rest/v1/finn_research_cache",
                params={"id": "eq." + private[0]["id"], "select": "id"},
            )
            require(
                response.status_code in {401, 403}
                or response.status_code == 200
                and response.json() == [],
                "An unpublished answer is publicly readable.",
            )
        return "RLS and anonymous private-table/unpublished-answer read denial verified without writes."

    report.check("Live database access safeguards", security)

    def budget():
        if not any(p.get("state") != "disabled" for p in profiles.values()):
            raise SkipCheck("Semantic retrieval disabled; no provider quota check was attempted.")
        value = store.rpc(
            "finn_embedding_budget", {"p_model": embeddings.model_name(), "p_rpd": 900}
        )
        require(
            isinstance(value.get("remaining"), int) and value["remaining"] >= 0,
            "Invalid application embedding-ledger response.",
        )
        return f"Application-ledger headroom: {value['remaining']} inputs. This is not a live Gemini quota probe."

    report.check("Recorded embedding budget", budget)
    checked_financial = {}
    for kind in ["financial_results", "financial_metrics"]:

        def financial(kind=kind):
            rows = store.rows(
                "finn_research_cache",
                **{"result->" + kind: "not.is.null"},
                select="result",
                order="created_at.desc",
                limit=3,
            )
            if not rows:
                raise SkipCheck(
                    "No saved " + kind + " case; no fresh calculation or ingestion was started."
                )
            answer = rows[0]["result"]
            valid_answer(answer, answer["symbol"])
            financial_metadata(answer)
            verify_evidence(answer)
            checked_financial[kind] = answer
            return "Retained units/basis/periods/formula inputs and live citation checked."

        report.check("Saved " + kind, financial)

        def cache_reuse(kind=kind):
            if kind not in checked_financial:
                raise SkipCheck("No verified saved case for this cache check.")
            answer = checked_financial[kind]
            first = fast_cached_research(store, answer["symbol"], answer["question"])
            if first:
                second = fast_cached_research(store, answer["symbol"], answer["question"])
                require(
                    first["cached"] and second and first["id"] == second["id"],
                    "Read-only fast-cache repeat did not preserve identity.",
                )
                return "Current fast-cache identity reused; no PDF/model/background work."
            raise SkipCheck(
                "Historical cache is not current; regeneration was deliberately not attempted."
            )

        report.check("Current fast-cache " + kind, cache_reuse)

    def fallback():
        available = [
            (symbol, p) for symbol, p in profiles.items() if p.get("index", {}).get("total")
        ]
        if not available:
            raise SkipCheck("No indexed corpus status available for a read-only fallback query.")
        modes = []
        for symbol, p in available:
            profile = {
                "mode": "hybrid" if p["state"] == "ready" else "keyword",
                "state": p["state"],
                "index": p["index"],
            }
            with patch.object(
                embeddings,
                "EmbeddingClient",
                side_effect=embeddings.EmbeddingUnavailable("sanity_simulated_quota_exhaustion"),
            ):
                result = retrieval.retrieve_with_diagnostics(
                    store, symbol, "Describe the business products and services.", profile=profile
                )
            require(
                result["mode"] == "keyword" and result["embedding_provider_calls"] == 0,
                "Embedding unavailability did not preserve keyword retrieval.",
            )
            require(
                result["fallback_reason"]
                == ("semantic_unavailable" if profile["mode"] == "hybrid" else "index_incomplete"),
                "Fallback reason did not match actual index coverage.",
            )
            modes.append(symbol + ": " + str(len(result["evidence"])) + " passages")
        return (
            "Local retrieval code against production corpus: "
            + ", ".join(modes)
            + ". Complete-index quota failure is injected; no quota consumed."
        )

    report.check("Read-only keyword fallback", fallback)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--local-only", action="store_true")
    mode.add_argument("--live-only", action="store_true")
    parser.add_argument("--public-only", action="store_true")
    parser.add_argument("--api-url")
    parser.add_argument("--symbols", nargs="+", default=["INFY", "CCL", "TMCV"])
    parser.add_argument("--timeout", type=float, default=20)
    args = parser.parse_args(argv)
    if not 1 <= args.timeout <= 120:
        parser.error("--timeout must be between 1 and 120 seconds.")
    if any(not re.fullmatch(r"[A-Z0-9&-]{1,30}", s) for s in args.symbols):
        parser.error("Use canonical NSE symbols.")
    load_local_env()
    report = Report()
    if not args.live_only:
        local_checks(report)
    if not args.local_only:
        url = args.api_url or os.getenv("FINN_DEPLOYED_API_URL") or os.getenv("VITE_API_BASE_URL")
        if not url:
            report.check(
                "Live checks",
                lambda: (_ for _ in ()).throw(
                    SkipCheck("No API URL configured; supply --api-url.")
                ),
            )
        else:
            try:
                live_checks(report, url, args.symbols, args.timeout, args.public_only)
            except Exception as exc:

                def failed(error=exc):
                    raise error

                report.check("Live check setup/execution", failed)
    return report.finish()


if __name__ == "__main__":
    raise SystemExit(main())
