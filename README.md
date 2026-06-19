# Native MCP for Home Assistant

<p align="center">
  <img src="https://raw.githubusercontent.com/czechbol/hass-mcp/refs/heads/main/assets/logo.svg" width="200" alt="Home Assistant MCP logo">
</p>

HACS-installable Home Assistant integration that mounts a **Model Context
Protocol** (MCP) server inside HA, exposing a small set of **generic
meta-tools** that cover the full HA admin surface — not the narrow LLM-API
subset that the core `mcp_server` integration provides.

- Mounted on HA's HTTP at `POST /api/hass_mcp` (Streamable HTTP, stateless,
  JSON-RPC body).
- Authentication: reuses HA bearer tokens (long-lived access tokens work).
- Transport: POST request → JSON response or `202 Accepted` for notifications.
  No SSE, no separate port.
- Coexists with HA's built-in `mcp_server` (which lives at `/api/mcp`).

## Documentation

- **[Quick start](docs/quickstart.md)** — zero → first tool call in 5 minutes.
- **[User guide](docs/user-guide.md)** — every tool, with examples and end-to-end workflows.
- **[Developer guide](docs/developer-guide.md)** — architecture, adding tools, running tests.
- **[Release process](docs/release.md)** — versioning, CHANGELOG, tags, HACS pickup.
- **[CHANGELOG](CHANGELOG.md)** — what's new.

## Install

1. Add this repository as a HACS custom repository (Integration).
2. Install **Native MCP for Home Assistant**, restart HA.
3. **Settings → Devices & Services → Add Integration → Native MCP for Home Assistant**.
   Toggle which tool classes are allowed: writes, destructive ops, firing
   arbitrary events.
4. Create a **long-lived access token** in your HA profile.
5. Point an MCP client at the endpoint:

   ```
   POST https://<your-ha>:8123/api/hass_mcp
   Authorization: Bearer <token>
   Content-Type: application/json
   ```

### Smoke test

```sh
curl -sS -X POST https://your-ha:8123/api/hass_mcp \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | jq .
```

### Claude Code / Claude Desktop

Add to your MCP client config:

```json
{
  "mcpServers": {
    "homeassistant": {
      "type": "http",
      "url": "https://your-ha:8123/api/hass_mcp",
      "headers": {
        "Authorization": "Bearer YOUR_LONG_LIVED_TOKEN"
      }
    }
  }
}
```

For clients that only speak stdio, wrap with
[`mcp-remote`](https://github.com/geelen/mcp-remote):

```json
{
  "homeassistant": {
    "command": "npx",
    "args": [
      "-y",
      "mcp-remote",
      "https://your-ha:8123/api/hass_mcp",
      "--header",
      "Authorization: Bearer YOUR_LONG_LIVED_TOKEN"
    ]
  }
}
```

## Tool reference

All tools live under the `ha_` prefix. List with `tools/list`; call with
`tools/call`. JSON Schema for every input is included in the listing.

| Tool                   | Purpose                                                                                                                              |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `ha_list_states`       | Filter+list entity states (domain / area / device / label / glob). Attributes omitted by default; `include_attributes=true` for full |
| `ha_get_state`         | Single entity state and attributes                                                                                                   |
| `ha_describe_entity`   | Rich introspection: state + attributes + decoded `supported_features` + registry/device/area join + available services               |
| `ha_set_state`         | Write to the state machine without invoking a device                                                                                 |
| `ha_delete_state`      | Remove entity from the state machine                                                                                                 |
| `ha_call_service`      | Call any HA service. `return_response` auto-detected from `supports_response`                                                        |
| `ha_list_services`     | Service catalog with field schemas, selectors, descriptions, targets — same data as HA UI. Filter to one service for by-id detail    |
| `ha_search`            | Fuzzy search across entities / devices / areas / labels                                                                              |
| `ha_render_template`   | Render an HA Jinja template                                                                                                          |
| `ha_validate_config`   | Validate trigger / condition / action blocks                                                                                         |
| `ha_yaml_config`       | CRUD for automations.yaml / scripts.yaml / scenes.yaml + auto-reload                                                                 |
| `ha_blueprint`         | List / get / import (url or yaml) / delete / substitute blueprints                                                                   |
| `ha_recorder`          | Info, purge, purge_entities                                                                                                          |
| `ha_energy`            | Energy dashboard prefs: get / save / validate                                                                                        |
| `ha_trace`             | Read automation/script execution traces (list/get/contexts)                                                                          |
| `ha_diagnostics`       | Per-integration / per-device diagnostics dump                                                                                        |
| `ha_helper`            | CRUD for input_boolean / input_number / input_select / input_text / input_datetime / counter / timer / schedule                      |
| `ha_backup`            | Backup integration: info/details/generate/delete/restore + agents/config                                                             |
| `ha_lovelace`          | Dashboards / configs / resources — read + CRUD (save/delete configs, create/update/delete dashboards & resources)                    |
| `ha_auth`              | Refresh + long-lived token mgmt (list/create/revoke)                                                                                 |
| `ha_webhook`           | List registered webhooks                                                                                                             |
| `ha_list_events`       | Event types + listener counts                                                                                                        |
| `ha_fire_event`        | Fire an event on the bus (gated)                                                                                                     |
| `ha_system`           | System introspection: op=get_config / check_config / get_health / read_error_log / read_system_log / clear_system_log |
| `ha_registry`          | Entity / device / area / label / floor / category / issue CRUD                                                                       |
| `ha_config_entries`    | Manage installed integrations: list / reload / unload / setup / remove / update_options                                              |
| `ha_config_flow`       | **Add new integrations** via the same flow the UI uses                                                                               |
| `ha_hacs`             | HACS: list/get/install/update repositories |
| `ha_history`          | Recorder timeline: kind=state_changes (significant state history) or kind=logbook (logbook events) between two timestamps |
| `ha_statistics`        | Long-term statistics: list_ids / period / metadata / clear                                                                           |
| `ha_assist`           | Invoke Assist: op=converse (conversation pipeline) or op=handle_intent (named intent like HassTurnOn) |
| `ha_camera_snapshot`   | Capture a camera frame as base64                                                                                                     |

### Adding a new integration via MCP

The `ha_config_flow` tool drives the same multi-step flow the UI uses:

```
ha_config_flow op=list_handlers          # discover available domains
ha_config_flow op=init domain=hue        # start a flow → returns flow_id
ha_config_flow op=configure flow_id=...  # submit user_input
```

Limitations:

- Adds integrations whose code is **already on disk**. It does not download
  packages — use HACS / pip for that.
- YAML-only integrations have no config flow.
- OAuth / external-step flows will surface the auth URL; you (the human) need
  to open it.

## Permissions model

Three integration options gate tool classes:

| Option              | Default | Tools it enables                                                                                                                |
| ------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `allow_write`       | ✅ on   | `ha_call_service`, `ha_set_state`, `ha_registry` updates, `ha_config_entries` mutations, `ha_config_flow`, `ha_assist` |
| `allow_destructive` | ❌ off  | `ha_delete_state`, `ha_registry` deletes                                                                                        |
| `allow_fire_event`  | ❌ off  | `ha_fire_event`                                                                                                                 |

The MCP server itself runs as the HA user who minted the token; all writes go
through HA's normal auth/permission machinery.

## Security notes

- Anyone with a long-lived token has root-equivalent control over HA.
  Issue tokens to clients you trust; rotate when revoking access.
- Only expose `/api/hass_mcp` over HTTPS in production.
- If you front HA with a reverse proxy, ensure the `Authorization` header is
  forwarded.

## Development

```sh
# Symlink into a dev HA config dir:
ln -s "$PWD/custom_components/hass_mcp" /path/to/ha-config/custom_components/hass_mcp
# Restart HA. Watch home-assistant.log for `hass_mcp: MCP endpoint registered`.
```

Quick interactive test with the MCP Inspector:

```sh
npx @modelcontextprotocol/inspector \
  --url https://your-ha:8123/api/hass_mcp \
  --header "Authorization: Bearer $HA_TOKEN"
```

## License

MIT
