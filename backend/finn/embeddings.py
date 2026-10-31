"""Small cached Gemini embedding client and resumable, bounded corpus backfill."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import logging
import math
import os
from threading import Event, Lock
import time
from urllib.parse import quote

import httpx

from finn.config import first_env, load_local_env
from finn.services import DependencyError, MissingConfiguration

DIMENSIONS = 768
VERSION = "gemini-retrieval-body-v1"
_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="finn-embeddings")
_scheduled: set[str] = set()
_lock = Lock()
_stop = Event()
_cooldowns: dict[str, float] = {}


def enabled() -> bool:
    return os.getenv("FINN_ENABLE_SEMANTIC_SEARCH", "false").lower() == "true"


def model_name() -> str:
    return os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EmbeddingUnavailable(DependencyError):
    def __init__(self, reason: str, retry_after=0):
        self.reason = reason
        self.retry_after = retry_after
        super().__init__("Semantic retrieval unavailable: " + reason)


def normalise(values) -> list[float]:
    if isinstance(values, str):
        values = json.loads(values)
    if (
        not isinstance(values, list)
        or len(values) != DIMENSIONS
        or any(
            isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v)
            for v in values
        )
    ):
        raise EmbeddingUnavailable("invalid_vector")
    length = math.sqrt(sum(v * v for v in values))
    if not math.isfinite(length) or length <= 1e-12:
        raise EmbeddingUnavailable("zero_vector")
    return [v / length for v in values]


def status(store, symbol: str | None) -> dict:
    result = store.rpc(
        "finn_embedding_status",
        {
            "p_symbol": symbol,
            "p_model": model_name(),
            "p_version": VERSION,
        },
    )
    if not result.get("secure"):
        raise EmbeddingUnavailable("index_access_policies")
    return result


class EmbeddingClient:
    def __init__(self, store, *, timeout=12):
        self.store = store
        self.model = model_name()
        key = first_env("GEMINI_API_KEY", "GOOGLE_API_KEY")
        if not key:
            raise MissingConfiguration("Embedding model is not configured.")
        self.client = httpx.Client(timeout=timeout, headers={"x-goog-api-key": key})
        self.calls = 0
        self.cache_hits = 0
        self._token_counts = {}
        self.daily_limit = 900

    def close(self):
        self.client.close()

    def _request(self, operation: str, payload: dict, *, count: int, tokens=0):
        with _lock:
            cooldown = _cooldowns.get(self.model, 0) - time.time()
        if cooldown > 0:
            raise EmbeddingUnavailable("provider_daily_budget", math.ceil(cooldown))
        reservation = self.store.rpc(
            "finn_reserve_embedding_request",
            {
                "p_model": self.model,
                "p_operation": "count" if operation == "countTokens" else "embed",
                "p_input_count": count,
                "p_tokens": tokens,
                "p_rpm": 80,
                "p_rpd": self.daily_limit,
                "p_tpm": 27000,
            },
        )
        if not reservation.get("allowed"):
            raise EmbeddingUnavailable(
                reservation.get("reason", "budget"), reservation.get("retry_after", 0)
            )
        self.calls += 1
        try:
            response = self.client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{quote(self.model, safe='-')}:{operation}",
                json=payload,
            )
        except httpx.HTTPError:
            raise EmbeddingUnavailable("provider_connection", 30) from None
        if response.status_code == 429:
            retry = response.headers.get("Retry-After", "60")
            delay = min(86400, int(retry)) if retry.isdigit() else 60
            daily = False
            try:
                details = response.json().get("error", {}).get("details", [])
                for detail in details:
                    if not isinstance(detail, dict):
                        continue
                    if "retryDelay" in detail:
                        delay = min(
                            86400,
                            max(1, math.ceil(float(str(detail["retryDelay"]).removesuffix("s")))),
                        )
                    daily |= any(
                        "perday" in str(v.get("quotaId", "")).lower()
                        for v in detail.get("violations", [])
                        if isinstance(v, dict)
                    )
            except (ValueError, TypeError, AttributeError):
                pass
            if daily:
                with _lock:
                    _cooldowns[self.model] = time.time() + delay
            raise EmbeddingUnavailable(
                "provider_daily_budget" if daily else "provider_throttled", delay
            )
        if response.is_error:
            raise EmbeddingUnavailable(
                "provider_http_" + str(response.status_code),
                30 if response.status_code >= 500 else 0,
            )
        try:
            result = response.json()
        except ValueError:
            raise EmbeddingUnavailable("invalid_provider_response") from None
        if not isinstance(result, dict):
            raise EmbeddingUnavailable("invalid_provider_response")
        return result

    def token_count(self, texts: list[str]) -> int:
        cache_key = tuple(text_hash(text) for text in texts)
        if cache_key in self._token_counts:
            return self._token_counts[cache_key]
        result = self._request(
            "countTokens",
            {"contents": [{"role": "user", "parts": [{"text": text}]} for text in texts]},
            count=len(texts),
        )
        count = result.get("totalTokens")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise EmbeddingUnavailable("invalid_token_count")
        self._token_counts[cache_key] = count
        return count

    def embed(self, texts: list[str], task: str) -> list[list[float]]:
        if task not in ["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"] or not texts or len(texts) > 32:
            raise ValueError("Invalid embedding batch/task.")
        if any(not text.strip() for text in texts):
            raise ValueError("Empty text cannot be embedded.")
        self.daily_limit = 800 if task == "RETRIEVAL_DOCUMENT" else 900
        hashes = [text_hash(text) for text in texts]
        unique = dict(zip(hashes, texts))
        cached = self.store.rows(
            "finn_embedding_cache",
            model="eq." + self.model,
            dimensions="eq.768",
            task_type="eq." + task,
            version="eq." + VERSION,
            input_hash="in.(" + ",".join(unique) + ")",
            select="input_hash,embedding",
        )
        vectors = {}
        for row in cached:
            try:
                vectors[row["input_hash"]] = normalise(row["embedding"])
                self.cache_hits += 1
            except (EmbeddingUnavailable, ValueError, TypeError):
                pass  # A corrupt cache entry is regenerated, never used for search.
        missing = [(digest, text) for digest, text in unique.items() if digest not in vectors]
        if missing:
            token_count = self.token_count([text for _, text in missing])
            # Byte fallback bounds small inputs. Count longer Unicode inputs individually
            # rather than silently accepting the model's 2,048-token truncation.
            for _, text in missing:
                if len(text.encode("utf-8")) > 2048 and self.token_count([text]) > 2048:
                    raise EmbeddingUnavailable("input_exceeds_model_limit")
            if len(missing) == 1 and token_count > 2048:
                raise EmbeddingUnavailable("input_exceeds_model_limit")
            result = self._request(
                "batchEmbedContents",
                {
                    "requests": [
                        {
                            "model": "models/" + self.model,
                            "content": {"parts": [{"text": text}]},
                            "taskType": task,
                            "outputDimensionality": DIMENSIONS,
                        }
                        for _, text in missing
                    ]
                },
                count=len(missing),
                tokens=math.ceil(token_count * 1.1) + 16 * len(missing),
            )
            generated = result.get("embeddings", [])
            if not isinstance(generated, list) or len(generated) != len(missing):
                raise EmbeddingUnavailable("incomplete_vector_batch")
            # Validate the entire batch before storing any result.
            validated = [
                normalise(row.get("values") if isinstance(row, dict) else None) for row in generated
            ]
            records = []
            for (digest, _), vector in zip(missing, validated):
                vectors[digest] = vector
                records.append(
                    {
                        "model": self.model,
                        "dimensions": DIMENSIONS,
                        "task_type": task,
                        "version": VERSION,
                        "input_hash": digest,
                        "embedding": vector,
                    }
                )
            self.store.upsert(
                "finn_embedding_cache",
                records,
                conflict="model,dimensions,task_type,version,input_hash",
                batch_size=32,
            )
        return [vectors[digest] for digest in hashes]


def backfill(
    store, symbol: str | None, *, max_batches=1000, wait=True, progress=lambda value: None
) -> dict:
    initial = status(store, symbol)
    client = EmbeddingClient(store, timeout=30)
    updated, reason, attempts = 0, None, 0
    batch_limit = 24
    try:
        while attempts < max_batches and not _stop.is_set():
            attempts += 1
            try:
                pending = store.rpc(
                    "finn_pending_embeddings",
                    {
                        "p_symbol": symbol,
                        "p_model": model_name(),
                        "p_version": VERSION,
                        "p_limit": batch_limit,
                    },
                )
                if not pending:
                    break
                vectors = client.embed([row["body"] for row in pending], "RETRIEVAL_DOCUMENT")
                for row, vector in zip(pending, vectors):
                    # Conditional update rejects a stale response after rechunking.
                    updated += bool(
                        store.rpc(
                            "finn_store_chunk_embedding",
                            {
                                "p_chunk_id": row["chunk_id"],
                                "p_input_hash": row["body_hash"],
                                "p_embedding": vector,
                                "p_model": model_name(),
                                "p_version": VERSION,
                            },
                        )
                    )
                progress(
                    {
                        "symbol": symbol,
                        "updated": updated,
                        "initial_ready": initial["ready"],
                        "total": initial["total"],
                    }
                )
            except EmbeddingUnavailable as exc:
                reason = exc.reason
                if reason == "batch_too_large" and batch_limit > 1:
                    batch_limit = max(1, batch_limit // 2)
                    continue
                if (
                    reason in ["daily_budget", "provider_daily_budget"]
                    or not wait
                    or exc.retry_after <= 0
                    or exc.retry_after > 120
                ):
                    break
                progress(
                    {
                        "symbol": symbol,
                        "updated": updated,
                        "waiting_seconds": exc.retry_after,
                        "reason": reason,
                    }
                )
                if _stop.wait(min(60, exc.retry_after)):
                    break
                reason = None
            except (httpx.HTTPError, DependencyError):
                reason = "storage_unavailable"
                if not wait:
                    break
                progress(
                    {"symbol": symbol, "updated": updated, "reason": reason, "waiting_seconds": 5}
                )
                if _stop.wait(5):
                    break
                reason = None
        final = status(store, symbol)
        return {
            **final,
            "updated": updated,
            "provider_calls": client.calls,
            "cache_hits": client.cache_hits,
            "state": "completed" if final["ready"] == final["total"] else "pending",
            "reason": reason,
        }
    finally:
        client.close()


def schedule_backfill(symbol: str):
    """One I/O-only worker; source acquisition and keyword answering never wait on it."""
    if not enabled() or _stop.is_set():
        return
    with _lock:
        if symbol in _scheduled:
            return
        _scheduled.add(symbol)

    def run():
        from finn.store import open_store

        try:
            with open_store() as store:
                current = status(store, symbol)
                if current["ready"] < current["total"]:
                    backfill(store, symbol)
        except Exception as exc:
            # Chunk state persists. A later request/CLI run resumes without re-embedding
            # completed text. Do not leak provider messages, inputs or credentials.
            logging.getLogger(__name__).warning(
                "Embedding backfill deferred (%s)", type(exc).__name__
            )
        finally:
            with _lock:
                _scheduled.discard(symbol)

    _pool.submit(run)


def stop_background():
    _stop.set()
    _pool.shutdown(wait=False, cancel_futures=True)


def main():
    from finn.store import open_store

    load_local_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True, help="NSE symbol, or ALL for active corpora")
    parser.add_argument("--max-batches", type=int, default=1000)
    parser.add_argument("--no-wait", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    symbol = None if args.symbol.upper() == "ALL" else args.symbol.upper().removesuffix(".NS")
    with open_store() as store:
        result = (
            status(store, symbol)
            if args.status
            else backfill(
                store,
                symbol,
                max_batches=args.max_batches,
                wait=not args.no_wait,
                progress=lambda value: print(json.dumps(value), flush=True),
            )
        )
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
