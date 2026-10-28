"""ha_system read_error_log tests: tail (default), head, and contains (grep).

Covers the 2.3.0 additions — the whole-file scan path for boot-time lines
(``head``) and substring filtering (``contains``) — alongside the original
fast-tail behavior.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.hass_mcp.tools import system

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
