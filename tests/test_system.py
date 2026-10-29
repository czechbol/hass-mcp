"""ha_system tests: read_error_log (tail/head/contains) and set_config.

Covers the read_error_log additions (whole-file scan for ``head`` and
``contains`` grep, alongside the original fast tail) and the ``set_config`` op
(field filtering, the empty-payload guard, and WS-error wrapping).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.hass_mcp.protocol import ToolError
from custom_components.hass_mcp.tools import system
from custom_components.hass_mcp.ws import WsCallError

_LOG = "\n".join(f"line{i:02d} {'go2rtc' if i == 3 else 'core'}" for i in range(1, 21))


class _Hass:
    """Minimal hass: a config.path pointing at the temp log and an executor that
    just runs the callable inline."""

    def __init__(self, path: str) -> None:
        self.config = SimpleNamespace(path=lambda _name: path)

    async def async_add_executor_job(self, func, *args):
        return func(*args)


@pytest.fixture
def logfile(tmp_path):
    p = tmp_path / "home-assistant.log"
    p.write_text(_LOG, encoding="utf-8")
    return str(p)


@pytest.mark.asyncio
async def test_tail_default(logfile):
    res = await system.ha_system(_Hass(logfile), op="read_error_log", lines=3)
    assert res["lines"] == ["line18 core", "line19 core", "line20 core"]
    assert res["count"] == 3


@pytest.mark.asyncio
async def test_head_reads_start(logfile):
    res = await system.ha_system(_Hass(logfile), op="read_error_log", lines=3, head=True)
    assert res["lines"] == ["line01 core", "line02 core", "line03 go2rtc"]


@pytest.mark.asyncio
async def test_contains_greps_whole_file(logfile):
    # 'go2rtc' is on an early line the tail window would miss.
    res = await system.ha_system(_Hass(logfile), op="read_error_log", lines=3, contains="go2rtc")
    assert res["lines"] == ["line03 go2rtc"]
    assert res["count"] == 1


@pytest.mark.asyncio
async def test_contains_is_case_insensitive(logfile):
    res = await system.ha_system(_Hass(logfile), op="read_error_log", lines=3, contains="GO2RTC")
    assert res["lines"] == ["line03 go2rtc"]


@pytest.mark.asyncio
async def test_contains_no_match_empty(logfile):
    res = await system.ha_system(_Hass(logfile), op="read_error_log", lines=3, contains="nope")
    assert res["lines"] == []
    assert res["count"] == 0


@pytest.mark.asyncio
async def test_missing_file_noted(tmp_path):
    missing = str(tmp_path / "absent.log")
    res = await system.ha_system(_Hass(missing), op="read_error_log", lines=3, contains="x")
    assert res["lines"] == []
    assert res["note"] == "log file does not exist"


@pytest.mark.asyncio
async def test_set_config_sends_known_fields(monkeypatch):
    seen = {}

    async def _fake_ws(hass, command, payload=None, **_kw):
        seen["command"] = command
        seen["payload"] = payload
        return None

    monkeypatch.setattr(system, "ws_call", _fake_ws)
    res = await system.ha_system(
        MagicMock(),
        op="set_config",
        data={"external_url": "https://ha.example.com", "internal_url": None, "bogus": "x"},
    )
    assert seen["command"] == "config/core/update"
    # Unknown keys dropped; a null URL (to clear it) is kept.
    assert seen["payload"] == {"external_url": "https://ha.example.com", "internal_url": None}
    assert res["updated"] == seen["payload"]


@pytest.mark.asyncio
async def test_set_config_requires_a_field(monkeypatch):
    monkeypatch.setattr(system, "ws_call", None)  # must not be called
    with pytest.raises(ToolError, match="requires at least one of"):
        await system.ha_system(MagicMock(), op="set_config", data={"bogus": "x"})


@pytest.mark.asyncio
async def test_set_config_wraps_ws_error(monkeypatch):
    async def _fake_ws(hass, command, payload=None, **_kw):
        raise WsCallError("invalid_info: bad url")

    monkeypatch.setattr(system, "ws_call", _fake_ws)
    with pytest.raises(ToolError, match="invalid_info"):
        await system.ha_system(MagicMock(), op="set_config", data={"external_url": "nope"})
