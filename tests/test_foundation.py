from decimal import Decimal
import io
from pathlib import Path

from fastapi.testclient import TestClient
import httpx
import pytest
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from finn.config import configuration_status
from finn.documents import (
    FinancialFact,
    citation_is_supported,
    comparison_blockers,
    extract_document,
)
from finn.main import app
from finn.sources import discover_documents, resolve_company


def test_health_does_not_claim_dependencies_are_verified():
    client = TestClient(app)
    assert client.get("/health/live").json()["status"] == "ok"
    readiness = client.get("/health/ready").json()
    assert readiness["dependencies_verified"] is False
    assert readiness["status"] == "configuration_only"


def test_cors_does_not_allow_arbitrary_browser_origins():
    client = TestClient(app)
    allowed = client.get("/health/live", headers={"Origin": "http://localhost:5173"})
    rejected = client.get("/health/live", headers={"Origin": "https://untrusted.example"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in rejected.headers


def test_render_frontend_has_no_privileged_environment_fields():
    import yaml

    blueprint = yaml.safe_load(Path("render.yaml").read_text())
    api, frontend = blueprint["services"]
    assert api["plan"] == "free"
    assert api["healthCheckPath"] == "/health/live"
    keys = {entry["key"] for entry in frontend["envVars"]}
    assert keys == {
        "NODE_VERSION",
        "VITE_API_BASE_URL",
        "VITE_SUPABASE_URL",
        "VITE_SUPABASE_PUBLISHABLE_KEY",
    }


def test_config_accepts_public_aliases_but_not_public_secret(monkeypatch):
    for key in [
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_ANON_KEY",
        "SUPABASE_PUBLISHABLE_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "public-key")
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_SECRET_KEY", "must-not-be-used")
    assert configuration_status()["supabase"] is False
    assert configuration_status()["public_cache"] is True


def test_generic_discovery_uses_only_primary_links():
    # Test-only synthetic HTML. This is never used as live/fallback data.
    html = """<h1>Unprepared company</h1><h3>Annual reports</h3><ul class="list-links"><li><a href="https://issuer.example/annual-2026.pdf">Annual Report 2026</a><a href="/summary/1">AI Summary</a></li></ul><h3>Concalls</h3><ul class="list-links"><li>Oct 2026<a href="https://issuer.example/transcript.pdf">Transcript</a><a href="/summary/2">AI Summary</a></li></ul>"""
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=html))
    )
    result = discover_documents(client, {"symbol": "UNPREPARED", "name": "Unprepared company"})
    assert result["documents"]["annual_report"][0]["source_url"].startswith(
        "https://issuer.example/"
    )
    assert result["documents"]["transcript"][0]["source_url"].endswith("transcript.pdf")
    assert result["documents"]["annual_report"][0]["reporting_period"] is None
    assert result["documents"]["annual_report"][0]["published_at"] is None
    assert len(result["documents"]["transcript"]) == 1


def test_missing_transcript_cannot_turn_into_summary():
    html = '<h3>Annual reports</h3><ul class="list-links"><li><a href="https://issuer.example/ar.pdf">Annual Report 2026</a></li></ul><h3>Concalls</h3><ul class="list-links"><li><a href="/summary/1">AI Summary</a></li></ul>'
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=html))
    )
    with pytest.raises(ValueError, match="no summary was substituted"):
        discover_documents(client, {"symbol": "ANY"})


def test_unknown_ticker_does_not_resolve_to_demo_company():
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, text="SYMBOL,NAME OF COMPANY,ISIN NUMBER\nKNOWN,Known Company,TEST\n"
            )
        )
    )
    with pytest.raises(ValueError, match="not found"):
        resolve_company(client, "UNKNOWN")


@pytest.mark.parametrize("native_text", [False, True])
def test_pdf_preserves_page_table_cells_and_ambiguity(native_text):
    out = io.BytesIO()
    document = SimpleDocTemplate(out)
    styles = getSampleStyleSheet()
    table = Table(
        [
            ["Metric", "FY 2026", "FY 2025"],
            ["Revenue", "1,200", "1,000"],
            ["Net loss", "(40)", "(20)"],
            ["Missing", "-", "nil"],
        ]
    )
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 1, colors.black)]))
    document.build(
        [
            Paragraph("SYNTHETIC TEST FIXTURE ONLY", styles["Title"]),
            Paragraph(
                "Consolidated financial statements. INR in crores. March 31, 2026.",
                styles["Normal"],
            ),
            Spacer(1, 20),
            table,
        ]
    )
    result = extract_document(
        out.getvalue(),
        {
            "source_url": "https://issuer.example/test.pdf",
            "reporting_period": None,
            "published_at": None,
        },
        native_text=native_text,
    )
    assert result["page_count"] == 1
    assert result["tables"][0]["pdf_page"] == 1
    assert result["tables"][0]["bbox"]
    assert any("(40)" in str(row) for row in result["tables"][0]["cells"])
    assert result["tables"][0]["approved_for_financial_comparison"] is False
    assert result["reporting_period"] is None


def test_citations_require_nonempty_source_quote():
    assert citation_is_supported("cash\n flow", "Operating cash flow improved.")
    assert not citation_is_supported("", "Anything")
    assert not citation_is_supported("Revenue rose 50%", "Revenue declined.")


def test_financial_comparison_rejects_ambiguous_extraction():
    base = dict(
        metric="revenue",
        raw_value="100",
        value=Decimal("100"),
        pdf_page=1,
        source_url="https://issuer.example/ar.pdf",
        evidence="Revenue 100",
    )
    a, b = FinancialFact(**base), FinancialFact(**base)
    assert comparison_blockers(a, b)
    complete = dict(
        period="FY2026",
        period_kind="annual",
        currency="INR",
        unit="crore",
        accounting_basis="consolidated",
        actual_or_guidance="actual",
        validated=True,
    )
    a, b = (
        FinancialFact(**base, **complete),
        FinancialFact(**base, **(complete | {"period": "FY2025"})),
    )
    assert comparison_blockers(a, b) == []
    assert "accounting_basis differs between the figures" in comparison_blockers(
        a, b.model_copy(update={"accounting_basis": "standalone"})
    )


def test_supabase_migration_does_not_allow_public_writes():
    sql = Path("supabase/migrations/0001_dependency_foundation.sql").read_text()
    assert "enable row level security" in sql
    assert "revoke all on public.finn_dependency_probes from anon, authenticated" in sql
    assert "for select to anon, authenticated" in sql
    assert "grant execute on function public.finn_dependency_capabilities() to service_role" in sql
