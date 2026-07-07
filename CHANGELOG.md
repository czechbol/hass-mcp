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

## [2.1.0] - 2026-07-02

### Security

- **Tool calls now execute as the token's owner, not a substituted admin.**
  Previously every WebSocket-backed call ran as the first active admin
  (`admins[0]`), so any valid bearer token gained admin rights. Calls now run
  as the Home Assistant user who owns the token, and HA's own permission
  machinery enforces that user's rights. Mutating operations **fail closed**
  when no authenticated user is present. `ha_auth` now acts on the calling
  token's own user (it too previously used `admins[0]`, letting any token mint
  an admin long-lived token).
- **Admin-only operations now require an admin token.** Tools that mutate via
  direct HA APIs with no per-user check of their own — `ha_registry`,
  `ha_config_entries`, `ha_config_flow`, `ha_energy`, `ha_statistics`,
  `ha_set_state`, `ha_delete_state`, `ha_yaml_config`, `ha_blueprint`,
  `ha_recorder`, `ha_system`, `ha_hacs` — now require the token's user to be an
  administrator (matching Home Assistant's own policy for those operations).
  Their read ops remain available to any token. In particular `ha_yaml_config`
  (automation/script authoring) and `ha_hacs op=download` (installs code) were
  previously reachable by any write-enabled token.
- `ha_blueprint` now rejects unsafe paths for **both** `op=import` (`filename`)
  and `op=delete` (`path`) — path separators that escape, `..` segments, and
  non-`.yaml` targets. Home Assistant's `async_remove_blueprint` performs an
  unsanitized path join + `unlink`, so `op=delete` was an arbitrary-file-delete
  vector; the guard closes it.
- `ha_hacs op=download` (installs integration code) is now classed **destructive**
  (default off) rather than a plain write.
- **Rate limiter now counts JSON-RPC batches.** A batch of N messages costs N
  slots and batches are capped (100), so a single request can no longer bypass
  the per-minute limit.
- **The endpoint fails closed when the integration is unloaded.** Previously the
  aiohttp view kept serving after unload and fell back to permissive option
  defaults (re-enabling writes); it now rejects requests until the entry is
  loaded again.
- **Destructive/write ops are now gated per `op`.** Several meta-tools
  (`ha_registry`, `ha_config_entries`, `ha_blueprint`, `ha_energy`,
  `ha_statistics`, `ha_helper`, `ha_backup`, `ha_yaml_config`) previously
  declared their gating only in prose or a coarse whole-tool flag, so
  create/update/delete/purge/restore could run with `allow_destructive` (or
  even `allow_write`) disabled. Gating is now declarative and enforced
  centrally before the handler runs.

### Changed

- Destructive ops (`delete` / `remove` / `purge` / `revoke` / `restore` /
  `clear`) now require `allow_destructive` (default **off**) rather than
  running under `allow_write`. Workflows that relied on the old behavior must
  enable the toggle.
- Meta-tool permission gating moved from whole-tool `requires_*` flags to
  declarative per-`op` `write_ops` / `destructive_ops`. This also fixes
  **over-gating**: `ha_recorder op=info` and `ha_hacs` read ops no longer
  require a write/destructive toggle and reappear in the default tool list.

## [2.0.0] - 2026-06-19

### Changed

- **Breaking — tool names.** Consolidated confusable tools into generic
  meta-tools to reduce `tools/list` context pollution. Clients that call the
  old names must migrate:
  - `ha_logbook` → `ha_history` with `kind=logbook` (state history is now
    `ha_history` with `kind=state_changes`).
  - `ha_conversation` → `ha_assist` with `op=converse`;
    `ha_intent` → `ha_assist` with `op=handle_intent`.
  - `ha_get_config` / `ha_check_config` / `ha_get_system_health` /
    `ha_error_log` / `ha_system_log` → `ha_system` with
    `op=get_config|check_config|get_health|read_error_log|read_system_log|clear_system_log`.
- `tools/list` now omits tools whose permission class is disabled
  (`allow_write`/`allow_destructive`/`allow_fire_event`) instead of listing
  them and failing the call. A default install lists ~28 tools instead of 32.
  Disabled capabilities are noted in the `initialize` instructions so they
  stay discoverable. Clients cache the list — reconnect after changing
  options to see the updated set.
- Slimmed the shared pagination fields (`limit`/`offset`) in tool schemas to
  trim catalog weight.
- Integration display name is now **Native MCP for Home Assistant**.

### Removed

- **Breaking** — `ha_describe_service`. Its output was byte-identical to a
  single row of `ha_list_services`; use
  `ha_list_services(domain="<d>", service_pattern="<d>.<s>")`.

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
