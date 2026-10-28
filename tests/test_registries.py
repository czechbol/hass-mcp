"""ha_registry mutation tests: enum coercion on entity/device update.

Covers the issue #2 fix: JSON string values for enum-typed registry fields are
coerced to their enum members before HA's ``async_update_*`` call; invalid
values raise ``ToolError``; ``None`` passes through unchanged.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.const import EntityCategory
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.hass_mcp.protocol import ToolError
from custom_components.hass_mcp.tools import registries


class _RegEntry:
    """Minimal entity-registry entry for ``_entity_to_dict``."""

    def __init__(self, entity_id: str) -> None:
        self.entity_id = entity_id
        self.unique_id = "uid"
        self.platform = "demo"
        self.config_entry_id = None
        self.device_id = None
        self.area_id = None
        self.disabled_by = None
        self.hidden_by = None
        self.name = None
        self.original_name = None
        self.icon = None
        self.labels = set()
        self.categories = {}
        self.options = {}


class _Device:
    """Minimal device-registry entry for ``_device_to_dict``."""

    def __init__(self, device_id: str) -> None:
        self.id = device_id
        self.name = None
        self.name_by_user = None
        self.manufacturer = None
        self.model = None
        self.sw_version = None
        self.hw_version = None
        self.area_id = None
        self.config_entries = set()
        self.connections = set()
        self.identifiers = set()
        self.labels = set()
        self.disabled_by = None


def _entity_reg(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    reg = MagicMock()
    reg.async_update_entity.return_value = _RegEntry("light.kitchen")
    monkeypatch.setattr(registries.er, "async_get", lambda hass: reg)
    return reg


def _device_reg(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    reg = MagicMock()
    reg.async_update_device.return_value = _Device("dev1")
    monkeypatch.setattr(registries.dr, "async_get", lambda hass: reg)
    return reg


@pytest.mark.asyncio
async def test_entity_list_filters_by_device(monkeypatch: pytest.MonkeyPatch) -> None:
    e1 = _RegEntry("light.a")
    e1.device_id = "dev1"
    e2 = _RegEntry("light.b")
    e2.device_id = "dev2"
    reg = MagicMock()
    reg.entities.values.return_value = [e1, e2]
    monkeypatch.setattr(registries.er, "async_get", lambda hass: reg)

    res = await registries.ha_registry(
        MagicMock(), kind="entity", op="list", data={"device_id": "dev1"}
    )
    ids = [row["entity_id"] for row in res["items"]]
    assert ids == ["light.a"]


@pytest.mark.asyncio
async def test_entity_list_no_filter_returns_all(monkeypatch: pytest.MonkeyPatch) -> None:
    reg = MagicMock()
    reg.entities.values.return_value = [_RegEntry("light.a"), _RegEntry("light.b")]
    monkeypatch.setattr(registries.er, "async_get", lambda hass: reg)

    res = await registries.ha_registry(MagicMock(), kind="entity", op="list")
    assert {row["entity_id"] for row in res["items"]} == {"light.a", "light.b"}


@pytest.mark.asyncio
async def test_entity_update_coerces_enum_strings(monkeypatch: pytest.MonkeyPatch) -> None:
    reg = _entity_reg(monkeypatch)
    await registries.ha_registry(
        MagicMock(),
        kind="entity",
        op="update",
        id="light.kitchen",
        data={
            "hidden_by": "user",
            "disabled_by": "user",
            "entity_category": "config",
        },
    )
    kwargs = reg.async_update_entity.call_args.kwargs
    assert kwargs["hidden_by"] is er.RegistryEntryHider.USER
    assert kwargs["disabled_by"] is er.RegistryEntryDisabler.USER
    assert kwargs["entity_category"] is EntityCategory.CONFIG


@pytest.mark.asyncio
async def test_entity_update_invalid_enum_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _entity_reg(monkeypatch)
    with pytest.raises(ToolError, match="invalid hidden_by 'bogus'"):
        await registries.ha_registry(
            MagicMock(),
            kind="entity",
            op="update",
            id="light.kitchen",
            data={"hidden_by": "bogus"},
        )


@pytest.mark.asyncio
async def test_entity_update_none_passes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    reg = _entity_reg(monkeypatch)
    await registries.ha_registry(
        MagicMock(),
        kind="entity",
        op="update",
        id="light.kitchen",
        data={"hidden_by": None, "name": "Kitchen"},
    )
    kwargs = reg.async_update_entity.call_args.kwargs
    assert kwargs["hidden_by"] is None
    assert kwargs["name"] == "Kitchen"


@pytest.mark.asyncio
async def test_device_update_coerces_enum_strings(monkeypatch: pytest.MonkeyPatch) -> None:
    reg = _device_reg(monkeypatch)
    await registries.ha_registry(
        MagicMock(),
        kind="device",
        op="update",
        id="dev1",
        data={"disabled_by": "user", "entry_type": "service"},
    )
    kwargs = reg.async_update_device.call_args.kwargs
    assert kwargs["disabled_by"] is dr.DeviceEntryDisabler.USER
    assert kwargs["entry_type"] is dr.DeviceEntryType.SERVICE


@pytest.mark.asyncio
async def test_device_update_invalid_enum_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _device_reg(monkeypatch)
    with pytest.raises(ToolError, match="invalid disabled_by 'bogus'"):
        await registries.ha_registry(
            MagicMock(),
            kind="device",
            op="update",
            id="dev1",
            data={"disabled_by": "bogus"},
        )


@pytest.mark.asyncio
async def test_device_update_none_passes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    reg = _device_reg(monkeypatch)
    await registries.ha_registry(
        MagicMock(),
        kind="device",
        op="update",
        id="dev1",
        data={"disabled_by": None, "name_by_user": "Hub"},
    )
    kwargs = reg.async_update_device.call_args.kwargs
    assert kwargs["disabled_by"] is None
    assert kwargs["name_by_user"] == "Hub"
