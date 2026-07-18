"""Per-entity read-permission filtering (POLICY_READ) across the read tools.

The write path gets per-entity enforcement for free (HA's entity_service_call
checks the context user). These tests cover the read side: a restricted
non-admin token must only observe entities its HA policy allows.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hass_mcp.identity import current_user
from custom_components.hass_mcp.protocol import ToolError
from custom_components.hass_mcp.tools import camera, describe, history, search, states
from custom_components.hass_mcp.tools import template as tmpl


class _Perms:
    """Fake HA permissions. ``allowed`` is True (all) or a set of entity_ids."""

    def __init__(self, allowed: object) -> None:
        self._allowed = allowed

    def check_entity(self, entity_id: str, key: str) -> bool:
        return True if self._allowed is True else entity_id in self._allowed

    def access_all_entities(self, key: str) -> bool:
        return self._allowed is True


class _User:
    def __init__(self, allowed: object, is_admin: bool = False) -> None:
        self.is_admin = is_admin
        self.permissions = _Perms(allowed)


@contextmanager
def _as(user: object):
    token = current_user.set(user)
    try:
        yield
    finally:
        current_user.reset(token)


class _State:
    def __init__(self, entity_id: str, state: str = "on", attributes: dict | None = None) -> None:
        self.entity_id = entity_id
        self.domain = entity_id.split(".")[0]
        self.state = state
        self.attributes = attributes or {}
        self.last_changed = None
        self.last_updated = None


def _hass_with(*entity_ids: str) -> MagicMock:
    objs = {eid: _State(eid) for eid in entity_ids}
    hass = MagicMock()
    hass.states.async_all.return_value = list(objs.values())
    hass.states.get.side_effect = lambda eid: objs.get(eid)
    return hass


# ---- ha_list_states -------------------------------------------------------


@pytest.mark.asyncio
async def test_list_states_filters_restricted_user() -> None:
    hass = _hass_with("light.kitchen", "device_tracker.dad", "camera.porch")
    with _as(_User(allowed={"light.kitchen"})):
        out = await states.ha_list_states(hass)
    ids = {i["entity_id"] for i in out["items"]}
    assert ids == {"light.kitchen"}


@pytest.mark.asyncio
async def test_list_states_admin_sees_all() -> None:
    hass = _hass_with("light.kitchen", "device_tracker.dad")
    with _as(_User(allowed=set(), is_admin=True)):
        out = await states.ha_list_states(hass)
    assert {i["entity_id"] for i in out["items"]} == {"light.kitchen", "device_tracker.dad"}


@pytest.mark.asyncio
async def test_list_states_no_user_allows_all() -> None:
    # Outside a request (unit-test direct call) there is no policy to apply.
    hass = _hass_with("light.kitchen", "device_tracker.dad")
    out = await states.ha_list_states(hass)
    assert len(out["items"]) == 2


# ---- ha_get_state ---------------------------------------------------------


@pytest.mark.asyncio
async def test_get_state_masks_unreadable_as_not_found() -> None:
    hass = _hass_with("device_tracker.dad")
    with _as(_User(allowed={"light.kitchen"})), pytest.raises(ToolError, match="not found"):
        await states.ha_get_state(hass, entity_id="device_tracker.dad")


@pytest.mark.asyncio
async def test_get_state_allows_readable() -> None:
    hass = _hass_with("light.kitchen")
    with _as(_User(allowed={"light.kitchen"})):
        out = await states.ha_get_state(hass, entity_id="light.kitchen")
    assert out["entity_id"] == "light.kitchen"


# ---- ha_describe_entity ---------------------------------------------------


@pytest.mark.asyncio
async def test_describe_masks_unreadable_as_not_found() -> None:
    hass = _hass_with("camera.bedroom")
    with _as(_User(allowed=set())), pytest.raises(ToolError, match="not found"):
        await describe.ha_describe_entity(hass, entity_id="camera.bedroom")


# ---- ha_search ------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_filters_entity_results() -> None:
    hass = _hass_with("light.kitchen_lamp", "light.bedroom_lamp")
    with _as(_User(allowed={"light.kitchen_lamp"})):
        out = await search.ha_search(hass, query="lamp", kinds=["entity"])
    assert {e["entity_id"] for e in out["entities"]} == {"light.kitchen_lamp"}


# ---- ha_camera_snapshot ---------------------------------------------------


@pytest.mark.asyncio
async def test_camera_snapshot_masks_unreadable() -> None:
    hass = _hass_with("camera.porch")
    with _as(_User(allowed=set())), pytest.raises(ToolError, match="not found"):
        await camera.ha_camera_snapshot(hass, entity_id="camera.porch")


# ---- ha_render_template ---------------------------------------------------


@pytest.mark.asyncio
async def test_template_blocked_for_restricted_user(monkeypatch: pytest.MonkeyPatch) -> None:
    # Even if a Template could be built, a restricted user is refused first.
    monkeypatch.setattr(tmpl.template_helper, "Template", lambda *a, **k: MagicMock())
    with _as(_User(allowed={"light.kitchen"})), pytest.raises(ToolError, match="unrestricted read"):
        await tmpl.ha_render_template(MagicMock(), template="{{ states }}")


@pytest.mark.asyncio
async def test_template_allowed_for_full_access_non_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = MagicMock()
    fake.async_render_will_timeout = AsyncMock(return_value=False)
    fake.async_render = MagicMock(return_value="ok")
    monkeypatch.setattr(tmpl.template_helper, "Template", lambda *a, **k: fake)
    with _as(_User(allowed=True)):  # non-admin, but full read policy
        out = await tmpl.ha_render_template(MagicMock(), template="{{ 1 }}")
    assert out == {"rendered": "ok"}


# ---- ha_history -----------------------------------------------------------


@pytest.mark.asyncio
async def test_history_state_changes_all_filtered_returns_empty() -> None:
    # All requested entities unreadable → empty result, no recorder access.
    with _as(_User(allowed=set())):
        out = await history.ha_history(
            MagicMock(), kind="state_changes", entity_ids=["device_tracker.dad"]
        )
    assert out["entities"] == {}


@pytest.mark.asyncio
async def test_history_logbook_rejects_device_ids_for_restricted_user() -> None:
    with _as(_User(allowed={"light.kitchen"})), pytest.raises(ToolError, match="device_ids"):
        await history.ha_history(MagicMock(), kind="logbook", device_ids=["dev-1"])
