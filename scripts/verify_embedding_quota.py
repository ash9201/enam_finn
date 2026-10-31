"""Check live batch-input accounting using isolated, promptly removed audit reservations."""

import json
import uuid

from finn.config import load_local_env
from finn.store import open_store


def main():
    load_local_env()
    results = {}
    with open_store() as store:
        for name, rpm, rpd, reason in [
            ("day", 80, 3, "daily_budget"),
            ("minute", 3, 100, "minute_budget"),
        ]:
            model = "finn-quota-audit-" + str(uuid.uuid4())
            values = {
                "p_model": model,
                "p_operation": "embed",
                "p_input_count": 2,
                "p_tokens": 1,
                "p_rpm": rpm,
                "p_rpd": rpd,
                "p_tpm": 27000,
            }
            try:
                first = store.rpc("finn_reserve_embedding_request", values)
                second = store.rpc("finn_reserve_embedding_request", values)
                results[name] = (
                    first.get("allowed") is True
                    and second.get("allowed") is False
                    and second.get("reason") == reason
                )
            finally:
                # These model names never call Gemini and cannot match application usage.
                store.delete("finn_embedding_requests", model="eq." + model)
    print(json.dumps(results))
    if not all(results.values()):
        raise SystemExit(
            "Apply 0007_embedding_input_quota.sql; batch-input accounting is not active."
        )


if __name__ == "__main__":
    main()
