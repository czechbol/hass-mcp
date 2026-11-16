"""Unit tests for ha_yaml_config's pure CRUD helpers.

These cover the list- vs dict-structured handling (automations.yaml is a list,
scripts.yaml is a mapping) without touching the filesystem or a reload.
"""

from __future__ import annotations

from custom_components.hass_mcp.tools.yaml_config import (
    _derive_entity_id,
    _find,
    _remove,
    _replace,
    _to_list,
)


def test_to_list_list_structure() -> None:
    data = [{"id": "a", "alias": "A"}, {"id": "b"}]
    assert _to_list(data, "list") == data


def test_to_list_dict_structure_injects_id() -> None:
    data = {"s1": {"sequence": []}, "s2": {"sequence": [1]}}
    out = _to_list(data, "dict")
    assert {"id": "s1", "sequence": []} in out
    assert {"id": "s2", "sequence": [1]} in out


def test_find_list_by_id_and_alias() -> None:
    data = [{"id": "a", "alias": "Morning"}]
    assert _find(data, "list", "a") == {"id": "a", "alias": "Morning"}
    assert _find(data, "list", "Morning") == {"id": "a", "alias": "Morning"}
    assert _find(data, "list", "missing") is None


def test_find_dict() -> None:
    data = {"s1": {"sequence": []}}
    assert _find(data, "dict", "s1") == {"id": "s1", "sequence": []}
    assert _find(data, "dict", "nope") is None


def test_replace_list_preserves_id() -> None:
    data = [{"id": "a", "alias": "old"}]
    assert _replace(data, "list", "a", {"id": "ignored", "alias": "new"}) is True
    assert data == [{"id": "a", "alias": "new"}]
    assert _replace(data, "list", "missing", {"alias": "x"}) is False


def test_replace_dict() -> None:
    data = {"s1": {"sequence": []}}
    assert _replace(data, "dict", "s1", {"sequence": [1]}) is True
    assert data == {"s1": {"sequence": [1]}}
    assert _replace(data, "dict", "s2", {"sequence": []}) is False


def test_remove_list_and_dict() -> None:
    data = [{"id": "a"}, {"id": "b"}]
    assert _remove(data, "list", "a") is True
    assert data == [{"id": "b"}]
    assert _remove(data, "list", "missing") is False


def test_derive_entity_id() -> None:
    # dict structure (scripts) slugifies the id itself.
    assert _derive_entity_id("script", "dict", "My Script", {}) == "script.my_script"
    # list structure (automations) slugifies the alias when present.
    assert (
        _derive_entity_id("automation", "list", "1700000000", {"alias": "Porch Light"})
        == "automation.porch_light"
    )
    # list structure falls back to the id when no alias.
    assert _derive_entity_id("automation", "list", "my_auto", {}) == "automation.my_auto"
