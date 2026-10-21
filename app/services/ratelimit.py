"""A small in-process rate limiter.

Scope and honesty: this holds counters in memory, so it is per-process and
resets when the app restarts or redeploys. On a single-instance deployment that
is enough to stop password guessing and OTP spraying. It is NOT a substitute for
a shared store (Redis) if this ever runs on more than one instance — at that
point each instance would enforce its own budget.

Used as a sliding window: `allow()` records a hit and reports whether the caller
is still inside its budget for the window.
"""
from __future__ import annotations

import threading
import time
from collections import deque

# Drop empty buckets once the table gets large, so a flood of distinct keys
# cannot grow this without bound.
_PRUNE_AT = 10_000


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        """Record a hit for `key`. Returns (allowed, retry_after_seconds).

        When the budget is spent, nothing is recorded and `retry_after` is how
        long until the oldest hit leaves the window.
        """
        now = time.monotonic()
        with self._lock:
            bucket = self._hits.get(key)
            if bucket is None:
                bucket = self._hits[key] = deque()
                if len(self._hits) > _PRUNE_AT:
                    self._prune(now)

            cutoff = now - window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                retry_after = int(bucket[0] + window - now) + 1
                return False, max(1, retry_after)

            bucket.append(now)
            return True, 0

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def clear(self) -> None:
        """Forget every counter. Used by the end-to-end test, which would
        otherwise be limited by its own previous run."""
        with self._lock:
            self._hits.clear()

    def _prune(self, now: float) -> None:
        """Drop buckets whose hits have all aged out. Caller holds the lock."""
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= now - 3600]:
            self._hits.pop(key, None)


limiter = RateLimiter()


def client_ip(request) -> str:
    """Best-effort client address for rate limiting.

    Behind a platform proxy (RumptyCloud) `request.client.host` is the proxy, so
    every visitor would share one budget. We therefore prefer the first entry of
    X-Forwarded-For, which is what the proxy saw. That header is only meaningful
    when a trusted proxy sets it — it is spoofable if the app is ever exposed
    directly, which is why every sensitive endpoint ALSO limits per email
    address, where spoofing is not possible.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    client = getattr(request, "client", None)
    return getattr(client, "host", "") or "unknown"


def too_many(retry_after: int) -> dict:
    """Standard 429 payload."""
    return {
        "detail": (
            "Too many attempts. Please wait "
            f"{retry_after} second{'s' if retry_after != 1 else ''} and try again."
        ),
        "retry_after": retry_after,
    }
