"""Per-token rate limiting for the MCP endpoint."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock


@dataclass(slots=True)
class _Bucket:
    timestamps: deque[float] = field(default_factory=deque)


class RateLimiter:
    """Sliding-window rate limiter keyed by an opaque token.

    ``max_calls`` requests allowed within any ``window_seconds`` window.
    """

    def __init__(self, max_calls: int, window_seconds: float) -> None:
        if max_calls < 1 or window_seconds <= 0:
            raise ValueError("max_calls>=1 and window_seconds>0 required")
        self.max_calls = max_calls
        self._window = window_seconds
        self._buckets: dict[str, _Bucket] = {}
        self._lock = Lock()
        self._checks = 0

    def check(self, key: str, cost: int = 1) -> tuple[bool, float]:
        """Record ``cost`` calls against ``key``. Returns (allowed, retry_after_seconds).

        ``cost`` > 1 is used for JSON-RPC batches so a single request can't run
        many messages for one slot. The whole batch is admitted or rejected
        atomically; nothing is recorded on rejection.
        """
        cost = max(1, cost)
        now = time.monotonic()
        with self._lock:
            self._checks += 1
            if self._checks % 1024 == 0:
                self._evict_idle(now)
            bucket = self._buckets.setdefault(key, _Bucket())
            cutoff = now - self._window
            while bucket.timestamps and bucket.timestamps[0] < cutoff:
                bucket.timestamps.popleft()
            if len(bucket.timestamps) + cost > self.max_calls:
                retry = self._window - (now - bucket.timestamps[0])
                return False, max(0.0, retry)
            bucket.timestamps.extend([now] * cost)
            return True, 0.0

    def _evict_idle(self, now: float) -> None:
        """Drop buckets whose entire window has expired (bounds memory).

        Callers keyed by transient tokens would otherwise accumulate forever.
        """
        cutoff = now - self._window
        stale = [
            k for k, b in self._buckets.items() if not b.timestamps or b.timestamps[-1] < cutoff
        ]
        for k in stale:
            del self._buckets[k]
