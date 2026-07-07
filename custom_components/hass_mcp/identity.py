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

from homeassistant.core import Context

# The HA User that owns the token for the current tool call, or None outside a
# request (e.g. a handler invoked directly in a unit test).
current_user: ContextVar[Any | None] = ContextVar("hass_mcp_current_user", default=None)


def effective_user() -> Any | None:
    """Return the user the current tool call executes as, or None."""
    return current_user.get()


def user_context() -> Context:
    """Build a Context attributed to the effective user for service calls."""
    user = current_user.get()
    return Context(user_id=user.id if user is not None else None)
