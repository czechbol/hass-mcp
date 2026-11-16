"""Unit tests for the in-process WebSocket dispatch (``ws.ws_call``).

These exercise ws.py's error/timeout/unwrap paths without a full Home Assistant
instance: ``hass`` is a MagicMock whose ``.data`` holds the WS handler registry
and whose ``.loop`` is the running loop (``ws_call`` builds its future from it).
``ws_call`` fails closed without an effective user, so the fixture sets the
identity contextvar to a dummy user for the duration, as a real request would.
Crafted handlers match the real ``_CaptureConnection`` callback signatures.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
import voluptuous as vol
from homeassistant.components.websocket_api import const as ws_const

from custom_components.hass_mcp import ws
from custom_components.hass_mcp.identity import current_user


@pytest.fixture
async def ws_hass():
    """MagicMock hass with a real WS registry + running loop and a user in context."""
    hass = MagicMock()
    hass.data = {ws_const.DOMAIN: {}}
    hass.loop = asyncio.get_running_loop()
    token = current_user.set(object())
    try:
        yield hass
    finally:
        current_user.reset(token)


def _register(hass, command, handler, schema=False):
    hass.data[ws_const.DOMAIN][command] = (handler, schema)


@pytest.mark.asyncio
async def test_unknown_command(ws_hass) -> None:
    with pytest.raises(ws.WsCallError, match="unknown WS command"):
        await ws.ws_call(ws_hass, "no/such")


@pytest.mark.asyncio
async def test_send_error_surfaces_code_and_message(ws_hass) -> None:
    def handler(hass, conn, msg):
        conn.send_error(msg["id"], "some_code", "some message")

    _register(ws_hass, "err/cmd", handler)
    with pytest.raises(ws.WsCallError, match="some_code: some message"):
        await ws.ws_call(ws_hass, "err/cmd")


@pytest.mark.asyncio
async def test_send_message_failure_envelope_is_unwrapped(ws_hass) -> None:
    def handler(hass, conn, msg):
        conn.send_message(
            {"type": "result", "success": False, "result": {"code": "x", "message": "y"}}
        )

    _register(ws_hass, "msg/cmd", handler)
    with pytest.raises(ws.WsCallError, match="x: y"):
        await ws.ws_call(ws_hass, "msg/cmd")


@pytest.mark.asyncio
async def test_handler_exception_is_generic_and_hides_detail(ws_hass) -> None:
    def handler(hass, conn, msg):
        raise RuntimeError("secret internal detail")

    _register(ws_hass, "boom/cmd", handler)
    with pytest.raises(ws.WsCallError) as ei:
        await ws.ws_call(ws_hass, "boom/cmd")
    text = str(ei.value)
    assert "failed; see Home Assistant logs" in text
    assert "secret internal detail" not in text


@pytest.mark.asyncio
async def test_invalid_schema_arguments(ws_hass) -> None:
    def schema(msg):
        raise vol.Invalid("bad field")

    _register(ws_hass, "sch/cmd", lambda h, c, m: None, schema)
    with pytest.raises(ws.WsCallError, match="invalid arguments"):
        await ws.ws_call(ws_hass, "sch/cmd", {"x": 1})


@pytest.mark.asyncio
async def test_timeout(ws_hass) -> None:
    def handler(hass, conn, msg):
        # Never resolves conn.future.
        pass

    _register(ws_hass, "slow/cmd", handler)
    with pytest.raises(ws.WsCallError, match="timed out"):
        await ws.ws_call(ws_hass, "slow/cmd", timeout=0.01)


@pytest.mark.asyncio
async def test_happy_path_send_result(ws_hass) -> None:
    def handler(hass, conn, msg):
        conn.send_result(msg["id"], {"hello": "world"})

    _register(ws_hass, "ok/cmd", handler)
    result = await ws.ws_call(ws_hass, "ok/cmd")
    assert result == {"hello": "world"}


@pytest.mark.asyncio
async def test_happy_path_async_handler(ws_hass) -> None:
    async def handler(hass, conn, msg):
        conn.send_result(msg["id"], {"async": True})

    _register(ws_hass, "async/cmd", handler)
    result = await ws.ws_call(ws_hass, "async/cmd")
    assert result == {"async": True}
