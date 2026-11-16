"""Shared JSON encoder default for MCP responses.

Both the wire serializer (``http.py``) and the tool-result text serializer
(``protocol.py``) encode the same kinds of Home Assistant objects, so the
``default`` hook lives here once rather than being duplicated (and drifting).
"""

from __future__ import annotations

import datetime as _dt
import enum as _enum
from types import MappingProxyType
from typing import Any


def json_default(o: Any) -> Any:
    """``json.dumps(default=...)`` hook for common HA/stdlib types."""
    if isinstance(o, MappingProxyType):
        return dict(o)
    if isinstance(o, (set, frozenset)):
        return sorted(o, key=str)
    if isinstance(o, (_dt.datetime, _dt.date, _dt.time)):
        return o.isoformat()
    if isinstance(o, _dt.timedelta):
        return o.total_seconds()
    if isinstance(o, _enum.Enum):
        return o.value
    if hasattr(o, "as_dict") and callable(o.as_dict):
        try:
            return o.as_dict()
        except Exception:  # noqa: BLE001
            pass
    if hasattr(o, "_asdict") and callable(o._asdict):
        try:
            return o._asdict()
        except Exception:  # noqa: BLE001
            pass
    return str(o)
