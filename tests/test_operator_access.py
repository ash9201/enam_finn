from fastapi.testclient import TestClient

from finn import api
from finn.main import app


def test_source_diagnostics_require_operator_key(monkeypatch):
    monkeypatch.setattr(
        api,
        "supabase_configuration",
        lambda: ("https://example.invalid", "private-operator-key", "public"),
    )
    with TestClient(app) as client:
        assert client.get("/internal/source-connectivity").status_code == 403
        assert (
            client.get(
                "/internal/source-connectivity", headers={"X-Finn-Admin-Key": "wrong"}
            ).status_code
            == 403
        )
