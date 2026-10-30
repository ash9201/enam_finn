import httpx
import pytest

from finn.sources import source_get


def test_transient_source_disconnect_recovers_once(monkeypatch):
    monkeypatch.setattr("finn.sources.time.sleep", lambda seconds: None)
    attempts = []

    def handler(request):
        attempts.append(request.url)
        if len(attempts) == 1:
            raise httpx.ConnectError("network unavailable", request=request)
        return httpx.Response(200, text="actual source")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert source_get(client, "https://example.com", "Document index").text == "actual source"
    assert len(attempts) == 2


def test_access_rejection_is_not_retried_or_disguised():
    attempts = []

    def handler(request):
        attempts.append(request.url)
        return httpx.Response(403)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="Document index returned HTTP 403"):
            source_get(client, "https://example.com", "Document index")
    assert len(attempts) == 1


def test_persistent_network_failure_names_the_unavailable_dependency(monkeypatch):
    monkeypatch.setattr("finn.sources.time.sleep", lambda seconds: None)

    def handler(request):
        raise httpx.ConnectError("Network is unreachable", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="NSE directory could not be reached"):
            source_get(client, "https://example.com", "NSE directory")
