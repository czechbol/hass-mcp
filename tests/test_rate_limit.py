"""RateLimiter unit tests (no HA fixtures needed)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.hass_mcp.rate_limit import RateLimiter


def test_allows_up_to_max() -> None:
    rl = RateLimiter(max_calls=3, window_seconds=60)
    assert rl.check("k")[0]
    assert rl.check("k")[0]
    assert rl.check("k")[0]


def test_blocks_after_max() -> None:
    rl = RateLimiter(max_calls=2, window_seconds=60)
    rl.check("k")
    rl.check("k")
    allowed, retry = rl.check("k")
    assert allowed is False
    assert retry > 0


def test_per_key_isolation() -> None:
    rl = RateLimiter(max_calls=1, window_seconds=60)
    assert rl.check("a")[0]
    assert rl.check("b")[0]
    assert rl.check("a")[0] is False


def test_window_resets() -> None:
    rl = RateLimiter(max_calls=1, window_seconds=60)
    with patch("custom_components.hass_mcp.rate_limit.time.monotonic", return_value=1000.0):
        assert rl.check("k")[0]
        assert rl.check("k")[0] is False
    with patch("custom_components.hass_mcp.rate_limit.time.monotonic", return_value=1061.0):
        assert rl.check("k")[0]


def test_cost_charges_multiple_slots() -> None:
    # A batch of N messages costs N slots (F-004: batches must not bypass).
    rl = RateLimiter(max_calls=10, window_seconds=60)
    assert rl.check("k", cost=8)[0]
    # Only 2 slots left → a cost-3 batch is rejected atomically...
    assert rl.check("k", cost=3)[0] is False
    # ...and nothing was recorded, so a cost-2 batch still fits.
    assert rl.check("k", cost=2)[0]
    assert rl.check("k")[0] is False


def test_cost_exceeds_max_on_empty_bucket() -> None:
    # cost > max_calls with an empty bucket must reject cleanly, not IndexError.
    rl = RateLimiter(max_calls=3, window_seconds=60)
    allowed, retry = rl.check("k", cost=5)
    assert allowed is False
    assert retry >= 0


def test_invalid_args() -> None:
    with pytest.raises(ValueError):
        RateLimiter(max_calls=0, window_seconds=60)
    with pytest.raises(ValueError):
        RateLimiter(max_calls=1, window_seconds=0)
