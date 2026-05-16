"""ha_auth — list/create/revoke long-lived access tokens + refresh tokens."""

from __future__ import annotations

import datetime as _dt
from typing import Any

from homeassistant.core import HomeAssistant

from ..protocol import ToolError
from ..registry import schema, tool

_OPS = ("current_user", "list_tokens", "create_long_lived_token", "delete_refresh_token")


@tool(
    name="ha_auth",
    description=(
        "Auth admin: list refresh / long-lived tokens for the current user, "
        "create new long-lived tokens, revoke tokens. NOTE: this acts on the "
        "user whose long-lived token was used to call MCP (i.e. yourself)."
    ),
    input_schema=schema(
        properties={
            "op": {"type": "string", "enum": list(_OPS)},
            "client_name": {
                "type": "string",
                "description": "Display name for op=create_long_lived_token.",
            },
            "client_icon": {"type": "string"},
            "lifespan_days": {
                "type": "integer",
                "minimum": 1,
                "maximum": 36500,
                "default": 365,
            },
            "refresh_token_id": {
                "type": "string",
                "description": "For op=delete_refresh_token.",
            },
        },
        required=["op"],
    ),
    read_only=False,
    destructive=True,
    requires_write=True,
    requires_destructive=True,
)
async def ha_auth(
    hass: HomeAssistant,
    op: str,
    client_name: str | None = None,
    client_icon: str | None = None,
    lifespan_days: int = 365,
    refresh_token_id: str | None = None,
) -> dict[str, Any]:
    if op not in _OPS:
        raise ToolError(f"unknown op '{op}'")

    # Get the user from the MCP integration's runtime data — falls back to
    # the first admin user if not available.
    user = None
    users = await hass.auth.async_get_users()
    admins = [u for u in users if u.is_active and u.is_admin]
    if not admins:
        raise ToolError("no admin user available")
    user = admins[0]

    if op == "current_user":
        return {
            "id": user.id,
            "name": user.name,
            "is_owner": user.is_owner,
            "is_admin": user.is_admin,
            "groups": [g.id for g in user.groups],
        }

    if op == "list_tokens":
        return {
            "tokens": [
                {
                    "id": t.id,
                    "type": str(t.token_type),
                    "client_name": t.client_name,
                    "client_icon": t.client_icon,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
                    "last_used_ip": t.last_used_ip,
                    "access_token_expiration_seconds": int(
                        t.access_token_expiration.total_seconds()
                    ),
                }
                for t in user.refresh_tokens.values()
            ]
        }

    if op == "create_long_lived_token":
        if not client_name:
            raise ToolError("op=create_long_lived_token requires client_name")
        from homeassistant.auth.const import MODELS_PASSWORD_RESET_BLOCK  # noqa: F401
        from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN

        try:
            refresh_token = await hass.auth.async_create_refresh_token(
                user,
                client_name=client_name,
                client_icon=client_icon,
                token_type=TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
                access_token_expiration=_dt.timedelta(days=lifespan_days),
            )
        except ValueError as e:
            raise ToolError(f"create failed: {e}") from e
        access_token = hass.auth.async_create_access_token(refresh_token)
        return {
            "refresh_token_id": refresh_token.id,
            "access_token": access_token,
            "client_name": refresh_token.client_name,
            "expires_in_seconds": int(refresh_token.access_token_expiration.total_seconds()),
        }

    if op == "delete_refresh_token":
        if not refresh_token_id:
            raise ToolError("op=delete_refresh_token requires refresh_token_id")
        token = user.refresh_tokens.get(refresh_token_id)
        if token is None:
            raise ToolError(f"refresh token '{refresh_token_id}' not found for user")
        await hass.auth.async_remove_refresh_token(token)
        return {"refresh_token_id": refresh_token_id, "deleted": True}

    raise ToolError(f"unsupported op '{op}'")
