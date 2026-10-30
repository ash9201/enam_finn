import httpx
import pytest

from finn.feasibility import Runner
from finn.services import DependencyError, require_ok


def test_failed_dependency_never_passes_the_gate(tmp_path):
    runner = Runner(tmp_path, 'TEST')
    runner.check('failed_live_source', lambda: (_ for _ in ()).throw(RuntimeError('source unavailable')))
    assert runner.finish() == 1
    assert runner.report['gate'] == 'not_verified'
    assert runner.report['checks'][0]['status'] == 'failed'
    assert 'evidence' not in runner.report['checks'][0]


def test_report_redacts_secrets_in_unexpected_error(tmp_path, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test-secret-never-print-this')
    runner = Runner(tmp_path, 'TEST')
    runner.check('failed', lambda: (_ for _ in ()).throw(RuntimeError('failure test-secret-never-print-this')))
    assert 'test-secret-never-print-this' not in (tmp_path / 'feasibility.json').read_text()


def test_optional_embedding_failure_does_not_prevent_keyword_foundation(tmp_path):
    runner = Runner(tmp_path, 'TEST')
    runner.check('required', lambda: {'ok': True})
    runner.check('embeddings', lambda: (_ for _ in ()).throw(RuntimeError('quota exhausted')), required=False)
    assert runner.finish() == 0


def test_http_auth_failure_does_not_echo_request_headers_or_url():
    response = httpx.Response(403, json={'error': {'status': 'PERMISSION_DENIED'}}, request=httpx.Request('POST', 'https://example.test/?key=secret-value', headers={'x-goog-api-key': 'secret-value'}))
    with pytest.raises(DependencyError) as error:
        require_ok(response, 'Gemini')
    assert 'secret-value' not in str(error.value)
    assert '403' in str(error.value)
