"""Small Supabase REST repository; privileged access stays on the server."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import hashlib
import os
from urllib.parse import quote

from finn.config import supabase_configuration
from finn.services import DependencyError, MissingConfiguration, require_ok, supabase_client


class Store:
    def __init__(self):
        url, secret, _ = supabase_configuration()
        if not url or not secret:
            raise MissingConfiguration("Server storage is not configured.")
        self.client = supabase_client(secret)

    def close(self):
        self.client.close()

    def rows(self, table: str, **params) -> list[dict]:
        response = self.client.get(f"rest/v1/{table}", params={"select": "*", **params})
        require_ok(response, "Database read")
        return response.json()

    def upsert(self, table: str, rows: list[dict], *, conflict="id", batch_size=70):
        for start in range(0, len(rows), batch_size):
            response = self.client.post(
                f"rest/v1/{table}",
                params={"on_conflict": conflict},
                json=rows[start : start + batch_size],
                headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            )
            require_ok(response, "Database upsert (apply the research migration if missing)")

    def patch(self, table: str, values: dict, **filters):
        response = self.client.patch(f"rest/v1/{table}", params=filters, json=values)
        require_ok(response, "Database update")

    def insert(self, table: str, row: dict):
        response = self.client.post(f"rest/v1/{table}", json=row)
        require_ok(response, "Database insert")

    def delete(self, table: str, **filters):
        if not filters:
            raise ValueError("Deleting managed evidence requires explicit filters.")
        response = self.client.delete(f"rest/v1/{table}", params=filters)
        require_ok(response, "Evidence index replacement")

    def rpc(self, name: str, values: dict):
        response = self.client.post(f"rest/v1/rpc/{name}", json=values)
        require_ok(response, "Database function (apply the research migration if missing)")
        return response.json()

    def put_pdf(self, path: str, data: bytes):
        bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "finn-documents")
        response = self.client.post(
            f"storage/v1/object/{quote(bucket, safe='')}/{path}",
            content=data,
            headers={"Content-Type": "application/pdf", "x-upsert": "false"},
        )
        try:
            duplicate = response.status_code == 409 or (
                response.status_code == 400 and str(response.json().get("statusCode")) == "409"
            )
        except ValueError:
            duplicate = False
        if duplicate:
            existing = self.client.get(f"storage/v1/object/{quote(bucket, safe='')}/{path}")
            require_ok(existing, "Existing private PDF integrity check")
            if hashlib.sha256(existing.content).digest() != hashlib.sha256(data).digest():
                raise DependencyError(
                    "A stored primary PDF does not match its content hash. It was not overwritten."
                )
        else:
            require_ok(response, "Private PDF upload")


@contextmanager
def open_store() -> Iterator[Store]:
    store = Store()
    try:
        yield store
    finally:
        store.close()
