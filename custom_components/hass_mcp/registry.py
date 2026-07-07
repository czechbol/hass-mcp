"""Tool registry for hass_mcp.

A tool is an async callable handler plus metadata (name, description, JSON Schema,
MCP tool annotations). Modules under ``tools/`` register their handlers at import
time via the :func:`tool` decorator; ``tools/__init__.py`` imports them all so a
single ``import hass_mcp.tools`` populates :data:`TOOLS`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant

Handler = Callable[..., Awaitable[Any]]


@dataclass(slots=True)
class ToolDef:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Handler
    output_schema: dict[str, Any] | None = None
    annotations: dict[str, Any] = field(default_factory=dict)
    # Tool-level permission class. Drives both tools/list filtering and
    # call-gating. Use for single-purpose tools whose whole surface is one
    # class (ha_set_state, ha_call_service, ha_fire_event, …).
    requires_write: bool = False
    requires_destructive: bool = False
    requires_fire_event: bool = False
    # Op-level permission classes for op-dispatch meta-tools. Maps the `op`
    # argument value to the class it needs. Gates the call only (never
    # tools/list — a meta-tool with gated ops still has readable ops). Ops not
    # listed here are treated as reads.
    write_ops: frozenset[str] = field(default_factory=frozenset)
    destructive_ops: frozenset[str] = field(default_factory=frozenset)
    # When True, any *mutating* action of this tool additionally requires the
    # effective user to be an administrator. Used for tools that mutate via
    # direct HA APIs (registry, config entries/flow, state machine, energy,
    # statistics) which have no per-user permission check of their own — these
    # operations are admin-only in Home Assistant. Reads are unaffected.
    requires_admin: bool = False

    def to_listing(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }
        if self.output_schema is not None:
            out["outputSchema"] = self.output_schema
        if self.annotations:
            out["annotations"] = self.annotations
        return out


TOOLS: dict[str, ToolDef] = {}


def tool(
    *,
    name: str,
    description: str,
    input_schema: dict[str, Any],
    output_schema: dict[str, Any] | None = None,
    read_only: bool = True,
    destructive: bool = False,
    idempotent: bool = True,
    open_world: bool = True,
    requires_write: bool = False,
    requires_destructive: bool = False,
    requires_fire_event: bool = False,
    requires_admin: bool = False,
    write_ops: list[str] | None = None,
    destructive_ops: list[str] | None = None,
) -> Callable[[Handler], Handler]:
    """Register an async tool handler.

    Handlers receive ``hass`` plus the validated input fields as kwargs and
    return JSON-serialisable data (typically a dict).

    ``write_ops`` / ``destructive_ops`` gate individual ``op`` values of an
    op-dispatch meta-tool. Prefer these over the tool-level ``requires_*``
    flags whenever a single tool mixes read and mutating ops.
    """

    def deco(func: Handler) -> Handler:
        if name in TOOLS:
            raise ValueError(f"tool {name!r} already registered")
        TOOLS[name] = ToolDef(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=func,
            output_schema=output_schema,
            annotations={
                "readOnlyHint": read_only,
                "destructiveHint": destructive,
                "idempotentHint": idempotent,
                "openWorldHint": open_world,
                "title": name,
            },
            requires_write=requires_write,
            requires_destructive=requires_destructive,
            requires_fire_event=requires_fire_event,
            requires_admin=requires_admin,
            write_ops=frozenset(write_ops or ()),
            destructive_ops=frozenset(destructive_ops or ()),
        )
        return func

    return deco


def schema(
    *,
    properties: dict[str, Any] | None = None,
    required: list[str] | None = None,
    additional_properties: bool = False,
) -> dict[str, Any]:
    """Convenience builder for an object JSON Schema."""
    out: dict[str, Any] = {
        "type": "object",
        "properties": properties or {},
        "additionalProperties": additional_properties,
    }
    if required:
        out["required"] = required
    return out


# Pagination fields are inlined into ~every tool's schema; kept minimal so they
# don't bloat the catalog. Bounds are enforced/tolerated by paginate(), not the
# schema. Names are self-describing, so no description.
LIMIT_FIELD: dict[str, Any] = {"type": "integer", "default": 100}

OFFSET_FIELD: dict[str, Any] = {"type": "integer", "default": 0}


def paginate(items: list[Any], limit: int, offset: int) -> dict[str, Any]:
    total = len(items)
    slice_ = items[offset : offset + limit]
    return {
        "items": slice_,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(slice_) < total,
        "next_offset": offset + len(slice_) if offset + len(slice_) < total else None,
    }


__all__ = [
    "LIMIT_FIELD",
    "OFFSET_FIELD",
    "TOOLS",
    "Handler",
    "HomeAssistant",
    "ToolDef",
    "paginate",
    "schema",
    "tool",
]
