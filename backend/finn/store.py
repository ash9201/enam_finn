"""Small Supabase REST repository; privileged access stays on the server."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import quote

import httpx

from finn.config import supabase_configuration
from finn.services import DependencyError, MissingConfiguration, require_ok, supabase_client
from finn.timing import span


class Store:
    def __init__(self):
        url, secret, _ = supabase_configuration()
        if not url or not secret:
            raise MissingConfiguration("Server storage is not configured.")
        self.client = supabase_client(secret)
        self.directory_cache_key = url.rstrip("/")

    def get_reference_snapshot(self, path):
        try:
            response = self.client.get(f"storage/v1/object/finn-reference/{path}", timeout=3)
        except httpx.HTTPError:
            raise DependencyError("Reference storage could not be reached.") from None
        if response.status_code in (400, 404):
            return None
        require_ok(response, "Reference directory read")
        return response.json()

    def put_reference_snapshot(self, path, value):
        # Official public reference data only. No anon write policies are granted.
        bucket = self.client.get("storage/v1/bucket/finn-reference")
        if bucket.status_code in (400, 404):
            created = self.client.post(
                "storage/v1/bucket",
                json={
                    "id": "finn-reference",
                    "name": "finn-reference",
                    "public": True,
                    "file_size_limit": 2 * 1024 * 1024,
                    "allowed_mime_types": ["application/json"],
                },
            )
            require_ok(created, "Public reference bucket creation")
        else:
            require_ok(bucket, "Reference bucket check")
        response = self.client.post(
            f"storage/v1/object/finn-reference/{path}",
            content=json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode(),
            headers={"Content-Type": "application/json", "x-upsert": "true"},
        )
        require_ok(response, "Verified directory publication")

    def close(self):
        self.client.close()

    def rows(self, table: str, **params) -> list[dict]:
        with span("cache_read" if table == "finn_research_cache" else "database_read"):
            try:
                response = self.client.get(f"rest/v1/{table}", params={"select": "*", **params})
            except (httpx.RemoteProtocolError, httpx.ConnectError):
                # Retry an interrupted read once. Quota RPCs are never retried.
                response = self.client.get(f"rest/v1/{table}", params={"select": "*", **params})
        require_ok(response, "Database read")
        return response.json()

    def upsert(self, table: str, rows: list[dict], *, conflict="id", batch_size=70):
        for start in range(0, len(rows), batch_size):
            with span("cache_write" if table == "finn_research_cache" else "database_write"):
                values = rows[start : start + batch_size]
                try:
                    response = self.client.post(
                        f"rest/v1/{table}",
                        params={"on_conflict": conflict},
                        json=values,
                        headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
                    )
                except (httpx.RemoteProtocolError, httpx.ConnectError):
                    # The same unique keys and values make this specific write
                    # idempotent, even if the first response was lost. No model
                    # call, insert or quota reservation is repeated.
                    response = self.client.post(
                        f"rest/v1/{table}",
                        params={"on_conflict": conflict},
                        json=values,
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
        with span("database_rpc"):
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

    def get_pdf(self, path, digest):
        bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "finn-documents")
        response = self.client.get(f"storage/v1/object/{quote(bucket, safe='')}/{path}")
        require_ok(response, "Stored primary PDF")
        if hashlib.sha256(response.content).hexdigest() != digest:
            raise DependencyError("The stored document failed its integrity check.")
        return response.content


@contextmanager
def open_store() -> Iterator[Store]:
    store = Store()
    try:
        yield store
    finally:
        store.close()
