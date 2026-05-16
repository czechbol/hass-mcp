"""Long-term statistics tool."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..protocol import ToolError
from ..registry import LIMIT_FIELD, OFFSET_FIELD, paginate, schema, tool

_OPS = {"list_ids", "period", "metadata", "clear"}


@tool(
    name="ha_statistics",
    description=(
        "Long-term statistics from the recorder. "
        "op=list_ids returns metadata for available statistic ids; "
        "op=period fetches values; op=metadata gets metadata for one id; "
        "op=clear deletes recorded statistics for given ids."
    ),
    input_schema=schema(
        properties={
            "op": {"type": "string", "enum": sorted(_OPS)},
            "statistic_ids": {"type": "array", "items": {"type": "string"}},
            "statistic_id_pattern": {
                "type": "string",
                "description": "Glob applied to statistic_id for op=list_ids (e.g. 'sensor.mikrotik_*').",
            },
            "start": {"type": "string"},
            "end": {"type": "string"},
            "period": {
                "type": "string",
                "enum": ["5minute", "hour", "day", "week", "month"],
                "default": "hour",
            },
            "types": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["change", "last_reset", "max", "mean", "min", "state", "sum"],
                },
            },
            "units": {
                "type": "object",
                "additionalProperties": {"type": "string"},
                "description": "Map of device_class to desired unit for conversion.",
            },
            "limit": LIMIT_FIELD,
            "offset": OFFSET_FIELD,
        },
        required=["op"],
    ),
    read_only=False,
)
async def ha_statistics(
    hass: HomeAssistant,
    op: str,
    statistic_ids: list[str] | None = None,
    statistic_id_pattern: str | None = None,
    start: str | None = None,
    end: str | None = None,
    period: str = "hour",
    types: list[str] | None = None,
    units: dict[str, str] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    import fnmatch

    if op not in _OPS:
        raise ToolError(f"unknown op '{op}'")

    try:
        from homeassistant.components.recorder import get_instance, statistics
    except ImportError as e:
        raise ToolError(f"recorder not loaded: {e}") from e

    instance = get_instance(hass)

    if op == "list_ids":

        def _fetch():
            return statistics.list_statistic_ids(hass, statistic_ids)

        rows = list(await instance.async_add_executor_job(_fetch))
        if statistic_id_pattern:
            rows = [
                r
                for r in rows
                if fnmatch.fnmatchcase(r.get("statistic_id", ""), statistic_id_pattern)
            ]
        return paginate(rows, limit, offset)

    if op == "metadata":
        if not statistic_ids:
            raise ToolError("op=metadata requires statistic_ids")

        def _fetch():
            return statistics.get_metadata(hass, statistic_ids=statistic_ids)

        meta = await instance.async_add_executor_job(_fetch)
        return {"metadata": meta}

    if op == "period":
        if not statistic_ids:
            raise ToolError("op=period requires statistic_ids")
        start_dt = dt_util.parse_datetime(start) if start else dt_util.utcnow() - timedelta(days=1)
        if start_dt is None:
            raise ToolError(f"could not parse start '{start}'")
        end_dt = dt_util.parse_datetime(end) if end else None
        types_set = set(types) if types else {"mean", "min", "max", "state", "sum", "change"}

        def _fetch():
            return statistics.statistics_during_period(
                hass,
                dt_util.as_utc(start_dt),
                dt_util.as_utc(end_dt) if end_dt else None,
                statistic_ids=set(statistic_ids),
                period=period,
                units=units,
                types=types_set,
            )

        rows = await instance.async_add_executor_job(_fetch)
        return {"period": period, "data": rows}

    if op == "clear":
        if not statistic_ids:
            raise ToolError("op=clear requires statistic_ids")

        def _do():
            statistics.clear_statistics(instance, statistic_ids)

        await instance.async_add_executor_job(_do)
        return {"cleared": statistic_ids}

    raise ToolError(f"unsupported op '{op}'")
