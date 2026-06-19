"""JSON-RPC dispatch unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.hass_mcp import protocol as protocol_mod
from custom_components.hass_mcp.protocol import dispatch
from custom_components.hass_mcp.registry import ToolDef, schema


@pytest.fixture
def hass() -> MagicMock:
    mock = MagicMock()
    mock.data = {protocol_mod.DOMAIN: {"options": {}}}
    return mock


@pytest.mark.asyncio
async def test_initialize(hass: MagicMock) -> None:
    response = await dispatch(
        hass,
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert response["result"]["protocolVersion"] == protocol_mod.PROTOCOL_VERSION
    assert "tools" in response["result"]["capabilities"]


@pytest.mark.asyncio
async def test_method_not_found(hass: MagicMock) -> None:
    response = await dispatch(
        hass,
        {"jsonrpc": "2.0", "id": 2, "method": "no_such_method"},
    )
    assert response["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_invalid_jsonrpc_version(hass: MagicMock) -> None:
    response = await dispatch(hass, {"jsonrpc": "1.0", "id": 3, "method": "ping"})
    assert response["error"]["code"] == -32600


@pytest.mark.asyncio
async def test_notification_returns_none(hass: MagicMock) -> None:
    # No "id" key → notification → no response.
    out = await dispatch(
        hass,
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    assert out is None


@pytest.mark.asyncio
async def test_tools_list_emits_registered(
    hass: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def handler(hass):
        return {"ok": True}

    fake_tools = {
        "ut_only": ToolDef(
            name="ut_only",
            description="d",
            input_schema=schema(),
            handler=handler,
        )
    }
    monkeypatch.setattr(protocol_mod, "TOOLS", fake_tools)

    response = await dispatch(
        hass,
        {"jsonrpc": "2.0", "id": 4, "method": "tools/list"},
    )
    names = [t["name"] for t in response["result"]["tools"]]
    assert names == ["ut_only"]


@pytest.mark.asyncio
async def test_tools_list_omits_disabled(hass: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    async def handler(hass):
        return {"ok": True}

    fake_tools = {
        "ut_read": ToolDef(
            name="ut_read",
            description="d",
            input_schema=schema(),
            handler=handler,
        ),
        "ut_destructive": ToolDef(
            name="ut_destructive",
            description="d",
            input_schema=schema(),
            handler=handler,
            requires_destructive=True,
        ),
    }
    monkeypatch.setattr(protocol_mod, "TOOLS", fake_tools)
    # Default options: allow_destructive off → destructive tool hidden from list.
    hass.data = {protocol_mod.DOMAIN: {"options": {}}}

    response = await dispatch(
        hass,
        {"jsonrpc": "2.0", "id": 8, "method": "tools/list"},
    )
    names = [t["name"] for t in response["result"]["tools"]]
    assert names == ["ut_read"]


@pytest.mark.asyncio
async def test_tools_call_executes_handler(
    hass: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def handler(hass, **kw):
        return {"echo": kw}

    fake_tools = {
        "ut_echo": ToolDef(
            name="ut_echo",
            description="d",
            input_schema=schema(properties={"x": {"type": "string"}}),
            handler=handler,
        )
    }
    monkeypatch.setattr(protocol_mod, "TOOLS", fake_tools)

    response = await dispatch(
        hass,
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "ut_echo", "arguments": {"x": "hi"}},
        },
    )
    result = response["result"]
    assert result["isError"] is False
    assert result["structuredContent"] == {"echo": {"x": "hi"}}


@pytest.mark.asyncio
async def test_tools_call_unknown_tool(hass: MagicMock) -> None:
    response = await dispatch(
        hass,
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "nope", "arguments": {}},
        },
    )
    assert response["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_tools_call_handler_raises_is_isolated(
    hass: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def bad(hass):
        raise RuntimeError("boom")

    fake_tools = {
        "ut_bad": ToolDef(
            name="ut_bad",
            description="d",
            input_schema=schema(),
            handler=bad,
        )
    }
    monkeypatch.setattr(protocol_mod, "TOOLS", fake_tools)

    response = await dispatch(
        hass,
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "ut_bad", "arguments": {}},
        },
    )
    # Tool failures surface as isError in result, not as JSON-RPC error envelope.
    assert "error" not in response
    assert response["result"]["isError"] is True
    assert "boom" in response["result"]["content"][0]["text"]
