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


def test_invalid_args() -> None:
    with pytest.raises(ValueError):
        RateLimiter(max_calls=0, window_seconds=60)
    with pytest.raises(ValueError):
        RateLimiter(max_calls=1, window_seconds=0)
