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

    def check(self, key: str) -> tuple[bool, float]:
        """Record one call against ``key``. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.setdefault(key, _Bucket())
            cutoff = now - self._window
            while bucket.timestamps and bucket.timestamps[0] < cutoff:
                bucket.timestamps.popleft()
            if len(bucket.timestamps) >= self.max_calls:
                retry = self._window - (now - bucket.timestamps[0])
                return False, max(0.0, retry)
            bucket.timestamps.append(now)
            return True, 0.0
