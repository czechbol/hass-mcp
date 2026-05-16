"""Internal WebSocket command dispatch.

Many HA features (helpers CRUD, backup, lovelace, system_log, auth) are
exposed only via WebSocket commands, not as HTTP REST or in-process helpers.
This module lets us invoke any registered WS command in-process with a fake
connection, capturing the response.
"""

from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol
from homeassistant.components.websocket_api import const as ws_const
from homeassistant.core import HomeAssistant, callback


class _CaptureConnection:
    """Stub ActiveConnection that captures send_result / send_error / send_message."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.user = None
        self.subscriptions: dict[Any, Any] = {}
        self.refresh_token_id = None
        self.future: asyncio.Future[Any] = hass.loop.create_future()

    @callback
    def send_result(self, msg_id: int, result: Any = None) -> None:
        if not self.future.done():
            self.future.set_result({"ok": True, "result": result})

    @callback
    def send_error(self, msg_id: int, code: str, message: str, *args: Any, **kw: Any) -> None:
        if not self.future.done():
            self.future.set_result({"ok": False, "code": code, "message": message})

    @callback
    def send_message(self, msg: Any) -> None:
        # Some handlers wrap themselves in a JSON-RPC envelope and call
        # send_message; unwrap to the actual result payload.
        if self.future.done():
            return
        payload = msg
        if isinstance(msg, dict) and msg.get("type") == "result":
            payload = msg.get("result")
            if not msg.get("success", True):
                self.future.set_result(
                    {
                        "ok": False,
                        "code": (payload or {}).get("code")
                        if isinstance(payload, dict)
                        else "error",
                        "message": (payload or {}).get("message")
                        if isinstance(payload, dict)
                        else str(payload),
                    }
                )
                return
        self.future.set_result({"ok": True, "result": payload})

    @callback
    def send_event(self, msg_id: int, data: Any) -> None:
        if not self.future.done():
            self.future.set_result({"ok": True, "result": data})

    def async_register_unsub(self, *_a, **_kw) -> None:  # pragma: no cover
        pass


class WsCallError(Exception):
    """Raised when an internal WS command returns an error response."""


async def ws_call(
    hass: HomeAssistant,
    command: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = 30,
) -> Any:
    """Invoke a registered WebSocket command and return the result.

    Raises :class:`WsCallError` if the handler emits an error response.
    """
    handlers: dict[str, tuple[Any, Any]] = hass.data.get(ws_const.DOMAIN, {})
    pair = handlers.get(command)
    if pair is None:
        raise WsCallError(f"unknown WS command '{command}'")
    handler, schema = pair

    msg: dict[str, Any] = {"id": 1, "type": command, **(payload or {})}
    # HA marks no-extra-args commands with `_ws_schema=False` (not None).
    if callable(schema):
        try:
            msg = schema(msg)
        except vol.Invalid as e:
            raise WsCallError(f"invalid arguments for '{command}': {e}") from e

    conn = _CaptureConnection(hass)
    # Populate an admin user so handlers decorated with @require_admin pass.
    # We trust the caller — the MCP integration already gated access via HA's
    # bearer-auth on the HomeAssistantView.
    try:
        users = await hass.auth.async_get_users()
        admins = [u for u in users if u.is_active and u.is_admin]
        if admins:
            conn.user = admins[0]
    except Exception:  # noqa: BLE001
        pass

    try:
        result = handler(hass, conn, msg)
    except Exception as e:
        raise WsCallError(f"{type(e).__name__}: {e}") from e
    if asyncio.iscoroutine(result):
        await result

    try:
        outcome = await asyncio.wait_for(conn.future, timeout=timeout)
    except TimeoutError as e:
        raise WsCallError(f"WS command '{command}' timed out after {timeout}s") from e

    if not outcome["ok"]:
        raise WsCallError(f"{outcome['code']}: {outcome['message']}")
    return outcome["result"]
