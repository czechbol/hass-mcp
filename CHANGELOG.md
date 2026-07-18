# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) ·
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security

- Read tools now honor the token owner's per-entity read policy (HA
  `POLICY_READ`), matching what the write path already enforced. A restricted
  non-admin token no longer sees entities its HA policy hides via
  `ha_list_states`, `ha_get_state`, `ha_describe_entity`, `ha_search`,
  `ha_camera_snapshot`, or `ha_history`. `ha_render_template` requires
  unrestricted read access (it reads state through an unfilterable channel).
  Admins, the owner, and default full-access users are unaffected.

## [2.1.0] - 2026-07-07

### Security

- Tool calls now execute as the token's owner instead of a substituted admin
  (`admins[0]`); `ha_auth` likewise acts on the caller. Mutating ops fail closed
  with no user.
- Admin-only operations now require an admin token: mutations on `ha_registry`,
  `ha_config_entries`, `ha_config_flow`, `ha_energy`, `ha_statistics`,
  `ha_set_state`, `ha_delete_state`, `ha_yaml_config`, `ha_blueprint`,
  `ha_recorder`, `ha_system`, `ha_hacs`, plus sensitive reads (`ha_system`
  logs/`get_config`, `ha_config_entries` list/get, `ha_diagnostics`).
- `ha_blueprint` import/delete reject path-traversal; `ha_hacs op=download`
  reclassified destructive; `ha_render_template` gains a best-effort render
  guard; `ha_fire_event` and `ha_config_flow`/`ha_diagnostics`/`ha_config_entries`
  reads are admin-gated.
- Rate limiter now counts JSON-RPC batches (capped at 100); the endpoint fails
  closed when the integration is unloaded.

### Changed

- Meta-tool permissions are gated per `op` via `write_ops`/`destructive_ops`.
  Destructive ops (delete/remove/purge/revoke/restore/clear) now require
  `allow_destructive` (default off) rather than `allow_write`.

## [2.0.0] - 2026-06-19

### Changed

- **Breaking — tool renames** (consolidated to shrink `tools/list`):
  - `ha_logbook` → `ha_history` (`kind=logbook`); state history is
    `ha_history` (`kind=state_changes`).
  - `ha_conversation`/`ha_intent` → `ha_assist` (`op=converse`/`handle_intent`).
  - `ha_get_config`/`ha_check_config`/`ha_get_system_health`/`ha_error_log`/
    `ha_system_log` → `ha_system` (`op=…`).
- `tools/list` now omits tools whose permission class is disabled (reconnect to
  refresh). Slimmed pagination fields in schemas.
- Integration display name is now **Native MCP for Home Assistant**.

### Removed

- **Breaking** — `ha_describe_service` (use `ha_list_services` with a
  `service_pattern`).

## [1.1.1] - 2026-05-17

### Fixed

- `ha_lovelace op=save_config` now parses YAML/JSON string inputs to a
  dict before passing to HA's `lovelace/config/save` WS command.
  Previously a raw string could be persisted verbatim, leaving the
  dashboard unrenderable (`Cannot use 'in' operator to search for
  'strategy' in <stringified-config>`). Non-mapping or unparseable
  strings now raise `ToolError` instead of bricking the dashboard.
- `ha_lovelace op=config` now materializes the `orjson.Fragment`
  returned by HA's lovelace handler into a plain dict. Previously
  clients received the Python repr `"<orjson.Fragment object at 0x…>"`
  through the MCP JSON encoder fallback.

### Changed

- `ha_lovelace` destructive-op error message now points to the
  integration's Configure dialog rather than implying the flag is a
  per-call argument.

## [1.1.0] - 2026-05-17

### Added

- `ha_lovelace` write ops: `save_config`, `delete_config`,
  `create_dashboard`, `update_dashboard`, `delete_dashboard`,
  `create_resource`, `update_resource`, `delete_resource`. Writes gated
  by `allow_write`; deletes additionally gated by `allow_destructive`.
  Storage-mode only for resource CRUD; YAML-mode dashboards reject
  save/delete (errors surface as `ToolError`).
- `CLAUDE.md` repo guide for future Claude Code sessions.

## [1.0.0] - 2026-05-17

Initial public release.

### Added

- HACS-installable HA integration mounting a stateless Streamable HTTP MCP
  server at `POST /api/hass_mcp`. Reuses HA bearer auth.
- 39 generic meta-tools covering states, services, registries (entity /
  device / area / label / floor / category / issue), automations / scripts
  / scenes (CRUD + traces), blueprints, helpers (input_* / counter / timer
  / schedule), history / logbook / statistics / recorder, diagnostics,
  system + error logs, lovelace, energy, conversation + intent, camera
  snapshots, webhooks, auth tokens, config entries, config flow
  (programmatic "Add Integration"), and HACS itself.
- Permission gates: `allow_write`, `allow_destructive`, `allow_fire_event`.
- Per-token sliding-window rate limiter (`rate_limit_per_minute`).
- Secret redaction in config-entry payloads.
- Per-call audit log line.
- In-process WebSocket dispatch helper (`ws.py`) for HA features without a
  Python API.
- Brand assets, CHANGELOG, LICENSE.
- Docs: quick start, user guide, developer guide, release process.
- CI: hassfest + HACS Action + ruff + pytest on every push.

[Unreleased]: https://github.com/czechbol/hass-mcp/compare/v2.1.0...HEAD
[2.1.0]: https://github.com/czechbol/hass-mcp/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/czechbol/hass-mcp/compare/v1.1.1...v2.0.0
[1.1.1]: https://github.com/czechbol/hass-mcp/releases/tag/v1.1.1
[1.1.0]: https://github.com/czechbol/hass-mcp/releases/tag/v1.1.0
[1.0.0]: https://github.com/czechbol/hass-mcp/releases/tag/v1.0.0
