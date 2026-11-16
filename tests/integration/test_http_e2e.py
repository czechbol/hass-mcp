"""End-to-end tests of the MCP HTTP transport (MCPView) over a real aiohttp app.

Everything else enters at protocol.dispatch(); these go through the actual HTTP
view via pytest-homeassistant's authenticated hass_client, exercising request
parsing, status codes, content-type, auth extraction, rate limiting, and the
on-the-wire JSON encoder — the layer a real MCP client actually talks to.
"""

from __future__ import annotations

import pytest
from homeassistant.setup import async_setup_component

from custom_components.hass_mcp.const import (
    CONF_ALLOW_WRITE,
    CONF_RATE_LIMIT_PER_MINUTE,
    DOMAIN,
    VIEW_URL,
)
from custom_components.hass_mcp.http import MCPView


async def _make_client(hass, hass_client, **options):
    from custom_components.hass_mcp import tools  # noqa: F401  side-effect: register tools

    assert await async_setup_component(hass, "http", {})
    opts = {CONF_ALLOW_WRITE: True, CONF_RATE_LIMIT_PER_MINUTE: 600}
    opts.update(options)
    hass.data[DOMAIN] = {"options": opts}
    hass.http.register_view(MCPView(hass))
    return await hass_client()


@pytest.mark.asyncio
async def test_initialize_over_http(hass, hass_client) -> None:
    client = await _make_client(hass, hass_client)
    resp = await client.post(
        VIEW_URL, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    )
    assert resp.status == 200
    assert resp.content_type == "application/json"
    body = await resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 1
    assert "result" in body
    assert "serverInfo" in body["result"]


@pytest.mark.asyncio
async def test_tools_call_round_trips_over_http(hass, hass_client) -> None:
    # A read tool whose result serializes through the wire encoder.
    client = await _make_client(hass, hass_client)
    resp = await client.post(
        VIEW_URL,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "ha_render_template", "arguments": {"template": "{{ 1 + 1 }}"}},
        },
    )
    assert resp.status == 200
    body = await resp.json()
    assert body["id"] == 2
    assert body["result"]["isError"] is False
    # structuredContent is the raw dict, serialized by the wire encoder.
    assert "2" in str(body["result"])


@pytest.mark.asyncio
async def test_notification_returns_202(hass, hass_client) -> None:
    client = await _make_client(hass, hass_client)
    # No "id" → notification → no response body.
    resp = await client.post(VIEW_URL, json={"jsonrpc": "2.0", "method": "ping"})
    assert resp.status == 202


@pytest.mark.asyncio
async def test_get_not_allowed(hass, hass_client) -> None:
    client = await _make_client(hass, hass_client)
    resp = await client.get(VIEW_URL)
    assert resp.status == 405
    assert resp.headers.get("Allow") == "POST"


@pytest.mark.asyncio
async def test_empty_body_is_400(hass, hass_client) -> None:
    client = await _make_client(hass, hass_client)
    resp = await client.post(VIEW_URL, data=b"")
    assert resp.status == 400


@pytest.mark.asyncio
async def test_invalid_json_is_400(hass, hass_client) -> None:
    client = await _make_client(hass, hass_client)
    resp = await client.post(VIEW_URL, data=b"{not json")
    assert resp.status == 400
    body = await resp.json()
    assert body["error"]["code"] == -32700


@pytest.mark.asyncio
async def test_batch_too_large_is_400(hass, hass_client) -> None:
    client = await _make_client(hass, hass_client)
    batch = [{"jsonrpc": "2.0", "id": i, "method": "ping"} for i in range(101)]
    resp = await client.post(VIEW_URL, json=batch)
    assert resp.status == 400


@pytest.mark.asyncio
async def test_unloaded_integration_is_503(hass, hass_client) -> None:
    client = await _make_client(hass, hass_client)
    hass.data.pop(DOMAIN, None)  # simulate entry unload
    resp = await client.post(VIEW_URL, json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert resp.status == 503


@pytest.mark.asyncio
async def test_batch_round_trips_over_http(hass, hass_client) -> None:
    client = await _make_client(hass, hass_client)
    batch = [
        {"jsonrpc": "2.0", "id": 1, "method": "ping"},
        {"jsonrpc": "2.0", "id": 2, "method": "ping"},
    ]
    resp = await client.post(VIEW_URL, json=batch)
    assert resp.status == 200
    assert resp.content_type == "application/json"
    body = await resp.json()
    assert isinstance(body, list)
    assert len(body) == 2
    assert {r["id"] for r in body} == {1, 2}


@pytest.mark.asyncio
async def test_rate_limit_returns_429_with_retry_after(hass, hass_client) -> None:
    client = await _make_client(hass, hass_client, rate_limit_per_minute=1)
    first = await client.post(VIEW_URL, json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert first.status == 200
    second = await client.post(VIEW_URL, json={"jsonrpc": "2.0", "id": 2, "method": "ping"})
    assert second.status == 429
    assert "Retry-After" in second.headers
