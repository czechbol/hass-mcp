# CLAUDE.md
This file provides guidance to Claude Code when working with code in this repository.

## What this is

HACS-installable Home Assistant custom integration that mounts a **Model Context
Protocol** (MCP) server inside HA at `POST /api/hass_mcp`. Exposes ~32 generic
meta-tools (`ha_*`) covering the full HA admin surface. Stateless Streamable
HTTP transport, JSON-RPC body, reuses HA bearer auth.

Single Python package: `custom_components/hass_mcp/`.

## Commands

```sh
ruff check .             # lint
ruff format --check .    # format check (use `ruff format .` to apply)
pytest -v                # full test suite
pytest tests/test_protocol.py::test_xyz -v   # single test
pip install -r requirements_test.txt         # install dev deps
```

CI runs `hassfest`, `hacs/action`, ruff, pytest on Python 3.13 — see
`.github/workflows/ci.yml`. `hassfest` and `hacs/action` are Docker-based;
don't bother running locally.

Dev install: symlink `custom_components/hass_mcp` into an HA config's
`custom_components/`, restart HA, watch log for `MCP endpoint registered`.

## Architecture

Request lifecycle: aiohttp POST → `MCPView` (`http.py`) → `RateLimiter`
(sliding-window, keyed on last 32 chars of bearer) → `protocol.dispatch`
(JSON-RPC: `initialize`, `tools/list`, `tools/call`, `ping`) →
`registry.TOOLS[name].handler(hass, **args)`.

Layout under `custom_components/hass_mcp/`:

- `__init__.py` — integration setup, option propagation into `hass.data`.
- `http.py` — `HomeAssistantView`, rate-limit gate, JSON encoder
  (`_json_default` handles `MappingProxyType`, `datetime`, `Enum`, `set`).
- `protocol.py` — JSON-RPC routing + `ToolError` wrap-to-`isError:true`.
- `registry.py` — `@tool` decorator, `ToolDef`, `schema()` helper,
  `LIMIT_FIELD` / `OFFSET_FIELD` / `paginate()`.
- `rate_limit.py` — per-key sliding-window limiter.
- `ws.py` — in-process WebSocket dispatch (`ws_call`) for HA features
  with no Python API (helpers, backup, lovelace, HACS, system_log, auth).
  Builds a fake `ActiveConnection` with an admin user.
- `config_flow.py` + `strings.json` + `translations/` — UI option form.
- `tools/` — one file per tool group; `tools/__init__.py` imports each
  module which side-effect-registers handlers via `@tool(...)`.

## Adding a tool

1. New file `tools/my_thing.py`, decorate handler with `@tool(name=..., description=..., input_schema=schema(...), read_only=..., requires_write=..., requires_destructive=..., requires_fire_event=...)`.
2. Add module import to `tools/__init__.py` (side-effect registers).
3. Update README tool table, `docs/user-guide.md`, `CHANGELOG.md` `[Unreleased]`.
4. Bump `manifest.json` `version` AND `const.SERVER_VERSION` — both. HA
   caches by version string; missing bump = stale bytecode on update.

Tool description is the agent's only hint — state WHEN to use it, name
required args. `ToolError` messages should name the next step
(e.g. "use `ha_list_services`").

## Conventions / gotchas

- **JSON Schema dicts** for tool inputs, not Pydantic.
- **Lazy-import** heavy HA components (`recorder`, `logbook`) inside the
  handler, not at module top.
- **Don't return raw HA objects**: `MappingProxyType`, `Enum`, `datetime`,
  `set` — convert to primitives or rely on `_json_default`.
- **Don't swallow `ToolError`**: permission gates are the user's only
  safeguard.
- Unit tests use plain `MagicMock` for `hass`; we deliberately skip
  `pytest-homeassistant-custom-component` fixtures for handler unit tests.
- Ruff config in `pyproject.toml` selects `E,F,W,I,B,UP,RUF,BLE,SLF`,
  target `py313`, line-length 100, `E501`/`B008` ignored.

## Permissions model

Three option flags gate tool classes:
`allow_write` (default on), `allow_destructive` (off), `allow_fire_event` (off).
Plus `rate_limit_per_minute` (default 600). Defined in `const.py`,
enforced in `protocol.py` per-tool via `ToolDef.requires_*` flags.

## Docs

`README.md`, `docs/quickstart.md`, `docs/user-guide.md`,
`docs/developer-guide.md` (deep dive on architecture + adding tools),
`docs/release.md`, `CHANGELOG.md`.
