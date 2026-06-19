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
    requires_write: bool = False
    requires_destructive: bool = False
    requires_fire_event: bool = False

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
) -> Callable[[Handler], Handler]:
    """Register an async tool handler.

    Handlers receive ``hass`` plus the validated input fields as kwargs and
    return JSON-serialisable data (typically a dict).
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
