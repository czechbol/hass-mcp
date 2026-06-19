"""Tool registration. Importing this package registers every tool."""

from __future__ import annotations

from . import (  # noqa: F401
    assist,
    auth_tokens,
    backup,
    blueprint,
    camera,
    config_entries,
    config_flow,
    describe,
    diagnostics,
    energy,
    events,
    hacs,
    helper_entities,
    history,
    lovelace,
    recorder,
    registries,
    search,
    services,
    states,
    statistics,
    system,
    template,
    trace,
    validate,
    webhook,
    yaml_config,
)
