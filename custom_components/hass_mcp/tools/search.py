"""ha_search — fuzzy search across entities, devices, areas, labels."""

from __future__ import annotations

import difflib
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
)
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers import (
    entity_registry as er,
)
from homeassistant.helpers import (
    label_registry as lr,
)

from ..registry import schema, tool

_KINDS = ("entity", "device", "area", "label")


@tool(
    name="ha_search",
    description=(
        "Fuzzy search across entities (by friendly_name + entity_id), devices "
        "(by name), areas, and labels. Returns top matches per kind. Use when "
        "the user gives a natural name like 'kitchen lamp' and you need the "
        "exact entity_id."
    ),
    input_schema=schema(
        properties={
            "query": {"type": "string", "description": "Free-text query."},
            "kinds": {
                "type": "array",
                "items": {"type": "string", "enum": list(_KINDS)},
                "description": "Restrict to these kinds (default: all).",
            },
            "limit_per_kind": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "default": 10,
            },
            "min_score": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "default": 0.4,
                "description": "Minimum similarity (0..1) to include a match.",
            },
        },
        required=["query"],
    ),
    read_only=True,
)
async def ha_search(
    hass: HomeAssistant,
    query: str,
    kinds: list[str] | None = None,
    limit_per_kind: int = 10,
    min_score: float = 0.4,
) -> dict[str, Any]:
    wanted = set(kinds) if kinds else set(_KINDS)
    out: dict[str, Any] = {"query": query}
    q = query.lower()

    def score(text: str) -> float:
        if not text:
            return 0.0
        t = text.lower()
        if q in t:
            # substring boost: rank by closeness to start, longer matches first
            return 0.9 + (0.1 if t.startswith(q) else 0.0)
        return difflib.SequenceMatcher(None, q, t).ratio()

    def top(items: list[tuple[float, dict[str, Any]]]) -> list[dict[str, Any]]:
        items.sort(key=lambda kv: kv[0], reverse=True)
        return [{**i, "score": round(s, 3)} for s, i in items[:limit_per_kind] if s >= min_score]

    if "entity" in wanted:
        results: list[tuple[float, dict[str, Any]]] = []
        for state in hass.states.async_all():
            fn = state.attributes.get("friendly_name") or ""
            s = max(score(fn), score(state.entity_id))
            if s >= min_score:
                results.append(
                    (s, {"entity_id": state.entity_id, "friendly_name": fn, "state": state.state})
                )
        out["entities"] = top(results)

    if "device" in wanted:
        reg = dr.async_get(hass)
        results = []
        for d in reg.devices.values():
            name = d.name_by_user or d.name or ""
            s = score(name)
            if s >= min_score:
                results.append(
                    (
                        s,
                        {
                            "id": d.id,
                            "name": name,
                            "manufacturer": d.manufacturer,
                            "model": d.model,
                            "area_id": d.area_id,
                        },
                    )
                )
        out["devices"] = top(results)

    if "area" in wanted:
        reg = ar.async_get(hass)
        results = []
        for a in reg.async_list_areas():
            s = max(score(a.name), max((score(al) for al in (a.aliases or [])), default=0.0))
            if s >= min_score:
                results.append((s, {"id": a.id, "name": a.name, "floor_id": a.floor_id}))
        out["areas"] = top(results)

    if "label" in wanted:
        reg = lr.async_get(hass)
        results = []
        for lab in reg.async_list_labels():
            s = score(lab.name)
            if s >= min_score:
                results.append((s, {"label_id": lab.label_id, "name": lab.name}))
        out["labels"] = top(results)

    return out


# Suppress unused-import warning for er; some future expansions will use it.
_ = er
