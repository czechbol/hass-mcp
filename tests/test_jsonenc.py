"""Tests for the shared JSON encoder default (jsonenc.json_default)."""

from __future__ import annotations

import datetime as dt
import enum
import json
from types import MappingProxyType

from custom_components.hass_mcp.jsonenc import json_default


class _Color(enum.Enum):
    RED = "red"


class _HasAsDict:
    def as_dict(self):
        return {"a": 1}


class _HasUnderscoreAsDict:
    # Not a tuple, so json can't serialize it natively — forces the _asdict
    # branch of the default hook.
    def _asdict(self):
        return {"x": 1, "y": 2}


def _roundtrip(value):
    return json.loads(json.dumps(value, default=json_default))


def test_mappingproxy():
    assert _roundtrip(MappingProxyType({"k": "v"})) == {"k": "v"}


def test_set_is_sorted():
    assert _roundtrip({3, 1, 2}) == [1, 2, 3]


def test_datetime_date_time():
    assert _roundtrip(dt.datetime(2026, 11, 16, 12, 0, 0)) == "2026-11-16T12:00:00"
    assert _roundtrip(dt.date(2026, 11, 16)) == "2026-11-16"
    assert _roundtrip(dt.time(8, 30)) == "08:30:00"


def test_timedelta_seconds():
    assert _roundtrip(dt.timedelta(minutes=2)) == 120.0


def test_enum_value():
    assert _roundtrip(_Color.RED) == "red"


def test_as_dict_object():
    assert _roundtrip(_HasAsDict()) == {"a": 1}


def test_underscore_asdict_branch():
    # The _asdict branch — previously only present in one of the two encoders.
    assert _roundtrip(_HasUnderscoreAsDict()) == {"x": 1, "y": 2}


def test_unknown_falls_back_to_str():
    class Weird:
        def __str__(self):
            return "weird"

    assert _roundtrip(Weird()) == "weird"
