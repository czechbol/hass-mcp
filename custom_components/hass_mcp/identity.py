"""Effective-user propagation for the in-flight tool call.

The MCP endpoint authenticates the bearer token at the HTTP layer; the owning
Home Assistant user is stashed here for the duration of a single ``tools/call``
so the two places that act on the caller's behalf — ``ws_call`` (sets
``conn.user``) and service calls (build a ``Context``) — run as that user
rather than a substituted admin.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.core import Context

# The HA User that owns the token for the current tool call, or None outside a
# request (e.g. a handler invoked directly in a unit test).
current_user: ContextVar[Any | None] = ContextVar("hass_mcp_current_user", default=None)


def effective_user() -> Any | None:
    """Return the user the current tool call executes as, or None."""
    return current_user.get()


def can_read_entity(entity_id: str) -> bool:
    """Whether the effective user may read ``entity_id`` (HA ``POLICY_READ``).

    Mirrors, for reads, what ``ha_call_service`` gets for free on writes: Home
    Assistant enforces the token owner's per-entity policy. Admins and the owner
    read everything. Outside a request (no user in context — e.g. a handler
    invoked directly in a unit test) there is no policy to apply, so allow;
    ``requires_auth=True`` guarantees a user on every real request.
    """
    user = current_user.get()
    if user is None or user.is_admin:
        return True
    return user.permissions.check_entity(entity_id, POLICY_READ)


def can_read_all_entities() -> bool:
    """Whether the effective user may read every entity.

    Fast path for list-style reads, and the gate for tools that read state
    through a channel we can't filter per-entity (Jinja templates).
    """
    user = current_user.get()
    if user is None or user.is_admin:
        return True
    return user.permissions.access_all_entities(POLICY_READ)


def user_context() -> Context:
    """Build a Context attributed to the effective user for service calls."""
    user = current_user.get()
    return Context(user_id=user.id if user is not None else None)
