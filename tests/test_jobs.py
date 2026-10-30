from finn import jobs


def test_restart_marks_only_the_same_services_abandoned_jobs_failed():
    class Store:
        def __init__(self):
            self.patches = []

        def rows(self, table, **params):
            return [
                {
                    "id": "interrupted",
                    "result": {"_service": jobs.SERVICE_SCOPE, "_worker": "old-process"},
                },
                {
                    "id": "current",
                    "result": {"_service": jobs.SERVICE_SCOPE, "_worker": jobs.INSTANCE_ID},
                },
                {
                    "id": "another-service",
                    "result": {"_service": "another-api", "_worker": "other-process"},
                },
            ]

        def patch(self, table, values, **params):
            self.patches.append((values, params))

    store = Store()
    jobs.expire_stale_jobs(store)
    targeted = [filters.get("id") for _, filters in store.patches if "id" in filters]
    assert targeted == ["eq.interrupted"]


def test_errors_never_return_configured_secrets(monkeypatch):
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "private-test-value-never-return-this")
    assert "private-test-value" not in jobs.safe_error(
        RuntimeError("Error: private-test-value-never-return-this")
    )


def test_redaction_precedes_truncation_and_handles_legacy_role_key(monkeypatch):
    secret = "legacy-private-role-key" * 12
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", secret)
    redacted = jobs.safe_error(RuntimeError("x" * 580 + secret))
    assert "legacy-private" not in redacted
    assert len(redacted) <= 600
