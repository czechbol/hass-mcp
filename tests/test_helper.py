"""ha_helper unit tests — validation + WS-command dispatch.

The real WS round-trip is covered in tests/integration; here we mock ws_call to
assert the handler validates inputs and dispatches the right command + payload
per op and kind.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.hass_mcp.protocol import ToolError
from custom_components.hass_mcp.tools.helper_entities import ha_helper


def _patch_ws(return_value=None):
    return patch(
        "custom_components.hass_mcp.tools.helper_entities.ws_call",
        new=AsyncMock(return_value=return_value),
    )


@pytest.mark.asyncio
async def test_unknown_kind_and_op() -> None:
    with pytest.raises(ToolError):
        await ha_helper(object(), kind="nope", op="list")
    with pytest.raises(ToolError):
        await ha_helper(object(), kind="counter", op="frobnicate")


@pytest.mark.asyncio
async def test_create_requires_name() -> None:
    with _patch_ws():
        with pytest.raises(ToolError):
            await ha_helper(object(), kind="input_boolean", op="create", config={})


@pytest.mark.asyncio
async def test_update_delete_require_id() -> None:
    with _patch_ws():
        with pytest.raises(ToolError):
            await ha_helper(object(), kind="counter", op="update", config={"name": "x"})
        with pytest.raises(ToolError):
            await ha_helper(object(), kind="counter", op="delete")


@pytest.mark.asyncio
async def test_list_dispatches_kind_list() -> None:
    with _patch_ws(return_value=[{"id": "a"}]) as p:
        result = await ha_helper(object(), kind="input_select", op="list")
    # ws_call(hass, "input_select/list")
    assert p.await_args.args[1] == "input_select/list"
    assert result["items"] == [{"id": "a"}]


@pytest.mark.asyncio
async def test_create_dispatches_with_config() -> None:
    cfg = {"name": "Mode", "options": ["a", "b"]}
    with _patch_ws(return_value={"id": "mode"}) as p:
        result = await ha_helper(object(), kind="input_select", op="create", config=cfg)
    assert p.await_args.args[1] == "input_select/create"
    assert p.await_args.args[2] == cfg
    assert result == {"created": True, "item": {"id": "mode"}}


@pytest.mark.asyncio
async def test_update_dispatches_with_kind_id_key() -> None:
    with _patch_ws(return_value={"id": "c1"}) as p:
        await ha_helper(object(), kind="counter", op="update", id="c1", config={"name": "New"})
    assert p.await_args.args[1] == "counter/update"
    assert p.await_args.args[2] == {"counter_id": "c1", "name": "New"}


@pytest.mark.asyncio
async def test_delete_dispatches_with_kind_id_key() -> None:
    with _patch_ws() as p:
        result = await ha_helper(object(), kind="timer", op="delete", id="t1")
    assert p.await_args.args[1] == "timer/delete"
    assert p.await_args.args[2] == {"timer_id": "t1"}
    assert result == {"deleted": True, "id": "t1"}
