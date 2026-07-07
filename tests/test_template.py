"""ha_render_template guard tests (regression for the missing-await bug)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hass_mcp.protocol import ToolError
from custom_components.hass_mcp.tools import template as tmpl


def _fake_template(monkeypatch, *, will_timeout: bool, value: str = "42"):
    fake = MagicMock()
    # async_render_will_timeout is a coroutine — the handler must await it.
    fake.async_render_will_timeout = AsyncMock(return_value=will_timeout)
    fake.async_render = MagicMock(return_value=value)
    monkeypatch.setattr(tmpl.template_helper, "Template", lambda *a, **k: fake)
    return fake


@pytest.mark.asyncio
async def test_render_returns_value_and_awaits_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_template(monkeypatch, will_timeout=False)
    out = await tmpl.ha_render_template(MagicMock(), template="{{ 40 + 2 }}")
    assert out == {"rendered": "42"}
    # Regression guard: the timeout check must actually be awaited (an unawaited
    # coroutine is truthy and would have rejected every render).
    fake.async_render_will_timeout.assert_awaited_once()


@pytest.mark.asyncio
async def test_render_rejects_when_would_time_out(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_template(monkeypatch, will_timeout=True)
    with pytest.raises(ToolError, match="exceeded"):
        await tmpl.ha_render_template(MagicMock(), template="{{ slow }}")
