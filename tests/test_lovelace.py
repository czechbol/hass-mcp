"""Unit tests for ha_lovelace tool."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.hass_mcp.const import CONF_ALLOW_DESTRUCTIVE, DOMAIN
from custom_components.hass_mcp.protocol import ToolError
from custom_components.hass_mcp.tools import lovelace as lovelace_mod
from custom_components.hass_mcp.tools.lovelace import ha_lovelace
from custom_components.hass_mcp.ws import WsCallError


@pytest.fixture
def hass() -> MagicMock:
    m = MagicMock()
    m.data = {DOMAIN: {"options": {}}}
    return m


@pytest.fixture
def capture(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any] | None]]:
    """Replace ws_call with a recorder; returns the call log."""
    calls: list[tuple[str, dict[str, Any] | None]] = []
    responses: dict[str, Any] = {
        "lovelace/info": {"mode": "storage"},
        "lovelace/dashboards/list": [{"id": "d1"}, {"id": "d2"}],
        "lovelace/config": {"views": []},
        "lovelace/resources": [{"id": "r1", "url": "/local/x.js"}],
        "lovelace/config/save": None,
        "lovelace/config/delete": None,
        "lovelace/dashboards/create": {"id": "d3"},
        "lovelace/dashboards/update": {"id": "d1", "title": "new"},
        "lovelace/dashboards/delete": None,
        "lovelace/resources/create": {"id": "r2"},
        "lovelace/resources/update": {"id": "r1"},
        "lovelace/resources/delete": None,
    }

    async def fake_ws_call(_hass, cmd: str, payload: dict[str, Any] | None = None) -> Any:
        calls.append((cmd, payload))
        if cmd not in responses:
            raise WsCallError(f"unknown WS command '{cmd}'")
        return responses[cmd]

    monkeypatch.setattr(lovelace_mod, "ws_call", fake_ws_call)
    return calls


# ---------- read ops ----------


async def test_info(hass: MagicMock, capture: list) -> None:
    result = await ha_lovelace(hass, op="info")
    assert result == {"mode": "storage"}
    assert capture == [("lovelace/info", None)]


async def test_dashboards_paginates(hass: MagicMock, capture: list) -> None:
    result = await ha_lovelace(hass, op="dashboards")
    assert result["total"] == 2
    assert result["items"] == [{"id": "d1"}, {"id": "d2"}]


async def test_config_with_url_path(hass: MagicMock, capture: list) -> None:
    await ha_lovelace(hass, op="config", url_path="energy")
    assert capture == [("lovelace/config", {"url_path": "energy"})]


async def test_config_default(hass: MagicMock, capture: list) -> None:
    await ha_lovelace(hass, op="config")
    assert capture == [("lovelace/config", {})]


async def test_resources_paginates(hass: MagicMock, capture: list) -> None:
    result = await ha_lovelace(hass, op="resources")
    assert result["total"] == 1


# ---------- write ops ----------


async def test_save_config_requires_config(hass: MagicMock, capture: list) -> None:
    with pytest.raises(ToolError) as exc:
        await ha_lovelace(hass, op="save_config", url_path="lovelace")
    assert "save_config" in str(exc.value)
    assert capture == []


async def test_save_config_with_payload(hass: MagicMock, capture: list) -> None:
    cfg = {"views": [{"title": "Home"}]}
    out = await ha_lovelace(hass, op="save_config", url_path="lovelace", config=cfg)
    assert out["ok"] is True
    assert capture == [("lovelace/config/save", {"config": cfg, "url_path": "lovelace"})]


async def test_save_config_yaml_string_is_parsed(hass: MagicMock, capture: list) -> None:
    yaml_in = "views:\n  - title: WAN\n    path: wan\n"
    await ha_lovelace(hass, op="save_config", url_path="wan", config=yaml_in)
    assert capture == [
        (
            "lovelace/config/save",
            {
                "config": {"views": [{"title": "WAN", "path": "wan"}]},
                "url_path": "wan",
            },
        )
    ]


async def test_save_config_json_string_is_parsed(hass: MagicMock, capture: list) -> None:
    json_in = '{"views":[{"title":"A","path":"a"}]}'
    await ha_lovelace(hass, op="save_config", config=json_in)
    assert capture == [
        (
            "lovelace/config/save",
            {"config": {"views": [{"title": "A", "path": "a"}]}},
        )
    ]


async def test_save_config_rejects_non_mapping_string(hass: MagicMock, capture: list) -> None:
    with pytest.raises(ToolError) as exc:
        await ha_lovelace(hass, op="save_config", config="just a string")
    assert "mapping" in str(exc.value)
    assert capture == []


async def test_save_config_rejects_invalid_yaml(hass: MagicMock, capture: list) -> None:
    with pytest.raises(ToolError):
        await ha_lovelace(hass, op="save_config", config="key: : :\n bad")
    assert capture == []


async def test_save_config_rejects_wrong_type(hass: MagicMock, capture: list) -> None:
    with pytest.raises(ToolError):
        await ha_lovelace(hass, op="save_config", config=42)
    assert capture == []


async def test_config_materializes_orjson_fragment(
    hass: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    import orjson

    fragment = orjson.Fragment(b'{"views":[{"title":"X"}]}')

    async def fake(_hass, _cmd, _payload=None):
        return fragment

    monkeypatch.setattr(lovelace_mod, "ws_call", fake)
    result = await ha_lovelace(hass, op="config", url_path="x")
    assert result == {"views": [{"title": "X"}]}


async def test_config_passes_through_dict(hass: MagicMock, capture: list) -> None:
    result = await ha_lovelace(hass, op="config", url_path="energy")
    assert result == {"views": []}


async def test_create_dashboard_requires_data(hass: MagicMock, capture: list) -> None:
    with pytest.raises(ToolError):
        await ha_lovelace(hass, op="create_dashboard")
    assert capture == []


async def test_create_dashboard(hass: MagicMock, capture: list) -> None:
    data = {
        "url_path": "test-dash",
        "title": "Test",
        "icon": "mdi:home",
        "mode": "storage",
        "show_in_sidebar": True,
        "require_admin": False,
    }
    result = await ha_lovelace(hass, op="create_dashboard", data=data)
    assert result == {"id": "d3"}
    assert capture == [("lovelace/dashboards/create", data)]


async def test_update_dashboard_requires_id(hass: MagicMock, capture: list) -> None:
    with pytest.raises(ToolError):
        await ha_lovelace(hass, op="update_dashboard", data={"title": "x"})
    assert capture == []


async def test_update_dashboard_requires_data(hass: MagicMock, capture: list) -> None:
    with pytest.raises(ToolError):
        await ha_lovelace(hass, op="update_dashboard", dashboard_id="d1")
    assert capture == []


async def test_update_dashboard(hass: MagicMock, capture: list) -> None:
    await ha_lovelace(hass, op="update_dashboard", dashboard_id="d1", data={"title": "new"})
    assert capture == [("lovelace/dashboards/update", {"dashboard_id": "d1", "title": "new"})]


async def test_create_resource(hass: MagicMock, capture: list) -> None:
    data = {"res_type": "module", "url": "/local/x.js"}
    await ha_lovelace(hass, op="create_resource", data=data)
    assert capture == [("lovelace/resources/create", data)]


async def test_update_resource(hass: MagicMock, capture: list) -> None:
    await ha_lovelace(
        hass,
        op="update_resource",
        resource_id="r1",
        data={"url": "/local/y.js"},
    )
    assert capture == [("lovelace/resources/update", {"resource_id": "r1", "url": "/local/y.js"})]


# ---------- destructive gating ----------


async def test_delete_dashboard_gated_off(hass: MagicMock, capture: list) -> None:
    # Destructive gating is enforced centrally (protocol._tools_call) from the
    # tool's declared destructive_ops — not inside the handler. With
    # allow_destructive off the op is rejected before the handler runs, so
    # ws_call is never reached.
    from custom_components.hass_mcp.protocol import dispatch
    from custom_components.hass_mcp.tools import lovelace  # noqa: F401  (register)

    resp = await dispatch(
        hass,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "ha_lovelace",
                "arguments": {"op": "delete_dashboard", "dashboard_id": "d1"},
            },
        },
        object(),  # user present → this exercises the op-gate, not fail-closed
    )
    assert resp["result"]["isError"] is True
    assert "destructive" in resp["result"]["content"][0]["text"]
    assert capture == []


async def test_delete_dashboard_gated_on(hass: MagicMock, capture: list) -> None:
    hass.data[DOMAIN]["options"][CONF_ALLOW_DESTRUCTIVE] = True
    out = await ha_lovelace(hass, op="delete_dashboard", dashboard_id="d1")
    assert out["ok"] is True
    assert capture == [("lovelace/dashboards/delete", {"dashboard_id": "d1"})]


async def test_delete_resource_gated_on(hass: MagicMock, capture: list) -> None:
    hass.data[DOMAIN]["options"][CONF_ALLOW_DESTRUCTIVE] = True
    await ha_lovelace(hass, op="delete_resource", resource_id="r1")
    assert capture == [("lovelace/resources/delete", {"resource_id": "r1"})]


async def test_delete_config_gated_on_with_url(hass: MagicMock, capture: list) -> None:
    hass.data[DOMAIN]["options"][CONF_ALLOW_DESTRUCTIVE] = True
    await ha_lovelace(hass, op="delete_config", url_path="lovelace")
    assert capture == [("lovelace/config/delete", {"url_path": "lovelace"})]


async def test_delete_dashboard_requires_id_even_when_allowed(
    hass: MagicMock, capture: list
) -> None:
    hass.data[DOMAIN]["options"][CONF_ALLOW_DESTRUCTIVE] = True
    with pytest.raises(ToolError):
        await ha_lovelace(hass, op="delete_dashboard")
    assert capture == []


# ---------- error paths ----------


async def test_unknown_op(hass: MagicMock, capture: list) -> None:
    with pytest.raises(ToolError) as exc:
        await ha_lovelace(hass, op="bogus")
    assert "unknown op" in str(exc.value)


async def test_ws_error_propagates(hass: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(_hass, _cmd, _payload=None):
        raise WsCallError("home_assistant_error: YAML mode")

    monkeypatch.setattr(lovelace_mod, "ws_call", fail)
    with pytest.raises(ToolError) as exc:
        await ha_lovelace(hass, op="save_config", config={"views": []})
    assert "YAML mode" in str(exc.value)


# ---------- registration ----------


def test_registered_with_write_gate() -> None:
    from custom_components.hass_mcp.registry import TOOLS

    # Ensure import has registered the tool.
    from custom_components.hass_mcp.tools import lovelace  # noqa: F401
    from custom_components.hass_mcp.tools.lovelace import _DESTRUCTIVE_OPS, _WRITE_OPS

    t = TOOLS["ha_lovelace"]
    # Gating is now per-op (write_ops / destructive_ops), not whole-tool.
    assert t.requires_write is False
    assert t.requires_destructive is False
    assert t.write_ops == frozenset(_WRITE_OPS)
    assert t.destructive_ops == frozenset(_DESTRUCTIVE_OPS)
    enum = t.input_schema["properties"]["op"]["enum"]
    for op in (
        "save_config",
        "delete_config",
        "create_dashboard",
        "update_dashboard",
        "delete_dashboard",
        "create_resource",
        "update_resource",
        "delete_resource",
    ):
        assert op in enum
