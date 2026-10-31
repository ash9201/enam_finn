"""Request-local measurements. Spans can overlap; no prompts, URLs or credentials are logged."""

import time
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

_current = ContextVar("finn_timing", default=None)


class Trace:
    def __init__(self, *, queue_ms=0):
        self.started = time.perf_counter()
        self.queue_ms = round(queue_ms)
        self.spans = []

    def summary(self):
        totals = {}
        for entry in self.spans:
            totals[entry["name"]] = round(totals.get(entry["name"], 0) + entry["ms"], 1)
        return {
            "queue_ms": self.queue_ms,
            "processing_ms": round((time.perf_counter() - self.started) * 1000),
            "span_ms": totals,
            "note": "Nested spans overlap; do not add them to total processing time.",
        }


@contextmanager
def tracing(*, queue_ms=0):
    trace = Trace(queue_ms=queue_ms)
    token = _current.set(trace)
    try:
        yield trace
    finally:
        _current.reset(token)


@contextmanager
def span(name):
    trace = _current.get()
    at = time.perf_counter()
    try:
        yield
    finally:
        if trace and len(trace.spans) < 1000:
            trace.spans.append({"name": name, "ms": (time.perf_counter() - at) * 1000})


def timed(name):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with span(name):
                return function(*args, **kwargs)

        return wrapped

    return decorate
