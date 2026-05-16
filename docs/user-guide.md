# User guide

This guide describes every tool the MCP server exposes, the permission gates
that govern them, and a handful of realistic end-to-end workflows.

Tools are grouped by domain. Inside each entry: what the tool does, the
required and most-useful arguments, and a representative example.

> **Convention.** Inputs use the same JSON Schema you'd see by calling
> `tools/list`. Examples below show only the `arguments` object — wrap it in
> `{"name": "<tool>", "arguments": {...}}` for the raw `tools/call` payload.

## Permissions model

Each tool is tagged with one or more capability flags. The integration owner
opts in to each class via the config flow:

| Flag | Default | Behavior |
|---|---|---|
| `allow_write` | ✅ on | Tools that mutate Home Assistant state |
| `allow_destructive` | ❌ off | Tools that delete state, registry rows, or recorder data |
| `allow_fire_event` | ❌ off | Raw event-bus writes (`ha_fire_event`) |

A gated tool returns an `isError:true` response with a hint telling the
caller which flag is missing — no silent failures.

The MCP server itself always runs as the user who minted the long-lived
token. Any further checks (entity permissions, area scopes) apply normally.

## Entity discovery

### `ha_list_states`

Filtered list of entity states. Filters compose with AND.

```json
{
  "domain": "light",
  "area": "Obývák",
  "label": "lights",
  "include_attributes": false
}
```

Default response is lean (`entity_id`, `state`, `friendly_name`, timestamps).
Pass `include_attributes: true` for the full attributes object — significant
payload increase, prefer `ha_get_state` for one entity.

### `ha_get_state`

Full state + attributes for a single entity. Always returns everything HA
has — use for follow-up after `ha_list_states`.

### `ha_describe_entity`

Rich introspection: state, attributes, decoded `supported_features` bitmask,
joined registry / device / area data, and the services callable on the
entity (with their target predicates). One call replaces five.

```json
{ "entity_id": "climate.kitchen_radiator" }
```

Returns `supported_features_decoded: ["TARGET_TEMPERATURE", "PRESET_MODE", "TURN_OFF", "TURN_ON"]`
plus `services: [ {id: "climate.set_temperature", target: {...supported_features: [1,2]}}, ... ]`.

### `ha_search`

Fuzzy search across **entities** (friendly name + entity_id), **devices**,
**areas**, **labels** in one call. Returns top-N per kind with similarity
scores.

```json
{ "query": "kitchen radiator", "limit_per_kind": 5, "min_score": 0.5 }
```

Use this when the human gives you a natural name and you need the exact
entity_id before calling other tools.

## Service catalog

### `ha_list_services`

Full service catalog with field schemas, selectors (color picker / numeric
slider / select options), examples, target shape, and `supports_response`.
This is the same data the HA UI's service-call dialog uses — translations
merged in.

Filter with `domain` or `service_pattern` glob (`light.*`, `*.turn_on`).

### `ha_describe_service`

One service by id (`light.turn_on`) — same shape as a single
`ha_list_services` row.

### `ha_call_service`

Calls a service. `return_response` is auto-detected from the service's
`supports_response` flag — only override when you really need to.

```json
{
  "domain": "light",
  "service": "turn_on",
  "target": { "entity_id": "light.svetlo_1" },
  "service_data": { "brightness_pct": 50, "color_temp_kelvin": 3000 }
}
```

Errors are wrapped — `HomeAssistantError`, voluptuous validation, unknown
service, unauthorized — all come back as `isError:true` with a readable
message.

## State machine writes

These mutate HA's in-memory state without invoking any device. Useful for
virtual sensors, MQTT-style synthetic entities, or overriding what an
integration reported.

- **`ha_set_state`** — write `state` + optional `attributes` for any entity_id.
- **`ha_delete_state`** — remove from the state machine. **Destructive** —
  requires `allow_destructive`.

Neither one touches the registry. To remove an entity definitively, use
`ha_registry kind=entity op=delete`.

## Registries

### `ha_registry`

One tool, seven kinds:

```json
{ "kind": "area", "op": "list" }
{ "kind": "device", "op": "get", "id": "<device-id>" }
{ "kind": "area", "op": "create", "data": { "name": "Office" } }
{ "kind": "label", "op": "delete", "id": "<label-id>" }
```

Kinds: `entity`, `device`, `area`, `label`, `floor`, `category`, `issue`.
Ops: `list`, `get`, `create`, `update`, `delete`. Not every kind supports
every op — `entity create` is rejected (entities come from platforms), the
`issue` registry is read-only.

`area`, `label`, and `floor` `get` accept either id or friendly name.

## Templates

### `ha_render_template`

Render a Home Assistant Jinja template. The single most powerful read tool:

```json
{
  "template": "{% set bad = states | selectattr('state','in',['unavailable','unknown']) | list %}{{ bad | length }}"
}
```

> **Sandbox caveat.** HA's template environment blocks `dict.update` and
> `list.append`. Use `namespace` for accumulators that *only* assign new
> variables — but `namespace.list.append(...)` still won't work. Prefer
> `groupby`, `selectattr`, list/dict comprehensions, and string-joined
> output.

## Automations, scripts, scenes

### `ha_yaml_config`

CRUD over `automations.yaml` / `scripts.yaml` / `scenes.yaml`. Validates
the parsed YAML, reloads the relevant domain on every mutation.

```json
{
  "kind": "automation",
  "op": "create",
  "config": {
    "alias": "Sunset lights",
    "triggers": [{ "trigger": "sun", "event": "sunset" }],
    "actions": [
      { "action": "scene.turn_on", "target": { "entity_id": "scene.evening" } }
    ],
    "mode": "single"
  }
}
```

The response includes the derived `entity_id` (`automation.sunset_lights`
in this case). Run `ha_validate_config` first to catch trigger / condition /
action errors before writing.

### `ha_validate_config`

Validate triggers, conditions, actions against HA's schemas without
mutating anything.

```json
{
  "triggers": [{ "trigger": "state", "entity_id": "binary_sensor.front_door", "to": "on" }],
  "actions":  [{ "action": "light.turn_on", "target": { "entity_id": "light.hall" } }]
}
```

### `ha_trace`

Read execution traces for an automation or script. Indispensable for
debugging "why didn't this fire?":

```json
{ "op": "list", "domain": "automation", "item_id": "nobody_home" }
{ "op": "get", "domain": "automation", "item_id": "nobody_home", "run_id": "..." }
```

### `ha_blueprint`

List, get, import (from URL or raw YAML), delete, substitute. Reads the
blueprint metadata (inputs + defaults) so an LLM can produce a valid
`use_blueprint:` automation without guessing.

## Helpers (`input_*`, counter, timer, schedule)

### `ha_helper`

Create, list, update, or delete helper entities. For setting their *value*
(e.g. flipping `input_boolean.away`), use `ha_call_service`.

```json
{ "kind": "input_boolean", "op": "create", "config": { "name": "Movie mode", "icon": "mdi:movie" } }
```

## History and stats

| Tool | Use |
|---|---|
| `ha_history` | Significant state changes between two ISO timestamps for given entity_ids |
| `ha_logbook` | Logbook entries (state changes formatted for humans) between two timestamps |
| `ha_statistics` | Long-term stats: `list_ids`, `period`, `metadata`, `clear` |
| `ha_recorder` | Recorder `info` + destructive `purge` / `purge_entities` |

`ha_statistics list_ids` accepts a `statistic_id_pattern` glob —
indispensable on big HA instances with hundreds of long-term stats.

## Conversation and intents

- **`ha_conversation`** — full Assist pipeline. Narrow intent grammar
  ("turn on the kitchen light"). Don't use it for open Q&A — use templates
  instead.
- **`ha_intent`** — lower-level intent handler (`HassTurnOn`, `HassGetState`,
  …). Bare slot values are auto-wrapped into `{value: x}`.

## System and audit

| Tool | What it does |
|---|---|
| `ha_get_config` | Core config (version, location, components, URLs) |
| `ha_check_config` | Validate `configuration.yaml` |
| `ha_get_system_health` | Aggregate `system_health/info` (HACS, recorder, network, cloud) |
| `ha_error_log` | Tail `home-assistant.log` |
| `ha_system_log` | HA's in-memory log entries (filterable by level / logger prefix) |
| `ha_diagnostics` | Per-integration / per-device diagnostics dump |
| `ha_list_events` | Event types currently subscribed, with listener counts |
| `ha_fire_event` | Fire arbitrary event (gated by `allow_fire_event`) |
| `ha_render_template` | (Repeat — also useful here for ad-hoc queries) |

## Integrations

### `ha_config_entries`

Manage already-installed integrations: `list`, `get`, `reload`, `unload`,
`setup`, `remove`, `update_options`. Sensitive fields in `data` and
`options` are auto-redacted (`password`, `token`, `secret`, etc.).

### `ha_config_flow`

Drive HA's "Add Integration" flow programmatically. Same multi-step UI
the user sees:

```json
{ "op": "list_handlers", "domain_pattern": "*hue*" }
{ "op": "init", "domain": "hue" }
{ "op": "configure", "flow_id": "...", "user_input": { "host": "..." } }
```

OAuth and external-step flows surface the auth URL for the human to open.

### `ha_hacs`

Drive HACS itself: list tracked repos, refresh upstream info, download a
version, fetch release notes.

```json
{ "op": "refresh", "repository": "1240881134" }
{ "op": "download", "repository": "1240881134", "version": "v0.5.2" }
```

This is what lets an LLM keep itself up to date.

## Lovelace and frontend

### `ha_lovelace`

Read-only: list dashboards, fetch a dashboard's config, list extra
resources.

## Auth and webhooks

### `ha_auth`

List / create / revoke refresh tokens and long-lived tokens for an admin
user.

```json
{ "op": "list_tokens" }
{ "op": "create_long_lived_token", "client_name": "claude-laptop", "lifespan_days": 90 }
{ "op": "delete_refresh_token", "refresh_token_id": "..." }
```

Acts on the first available admin user — typically the system owner.

### `ha_webhook`

List currently registered webhooks (id, integration, allowed methods).
Useful for finding webhook URLs handed to external services.

## Energy

### `ha_energy`

`get_prefs` / `save_prefs` / `validate` for the Energy dashboard.

## Camera

### `ha_camera_snapshot`

Capture a single frame as base64. Multimodal models can read it directly.

## Backups

### `ha_backup`

`info`, `details`, `generate`, `delete`, `restore`, plus `agents_info`
(configured storage agents) and `config_info` (auto-backup schedule).

```json
{ "op": "generate", "agent_ids": ["backup.local"], "name": "pre-update" }
```

---

# Workflows

## Audit unavailable entities

```
1. ha_render_template ⇒ count + breakdown by domain of unavailable/unknown entities
2. ha_render_template ⇒ list non-device_tracker bad entities
3. (cluster by prefix in your head) ⇒ pinpoint which integrations are degraded
4. ha_diagnostics op=config_entry entry_id=<offending one> ⇒ confirm root cause
5. ha_error_log ⇒ correlate timestamps
```

## Create an automation, verify, then delete it

```
1. ha_validate_config triggers=[…] actions=[…]   # syntax check
2. ha_yaml_config kind=automation op=create config={…}
3. → response.entity_id  (e.g. automation.my_new_thing)
4. ha_call_service automation.trigger target.entity_id=automation.my_new_thing
5. ha_trace op=list domain=automation item_id=my_new_thing → run_id
6. ha_trace op=get … run_id=… → confirm action fired
7. ha_yaml_config kind=automation op=delete id=…
```

## Drive your own HACS update

```
1. ha_hacs op=list name_contains="<repo-name>"      # find repository id
2. ha_hacs op=refresh repository=<id>               # fetch upstream
3. ha_hacs op=repository_info repository=<id>       # confirm available_version
4. ha_hacs op=download repository=<id>              # install latest
5. ha_call_service homeassistant.restart            # reload
```

## Find an entity by natural name and command it

```
1. ha_search query="bedroom lamp"                   # → light.bedside_lamp
2. ha_describe_entity entity_id=light.bedside_lamp  # → supported_features, services
3. ha_call_service light.turn_on target.entity_id=light.bedside_lamp \
     service_data={brightness_pct:30, color_temp_kelvin:2700}
```

## Inspect an integration's full state

```
1. ha_config_entries op=list domain=mikrotik_router
2. ha_diagnostics op=config_entry entry_id=<…>
3. ha_system_log op=list logger_prefix=custom_components.mikrotik_router
```

## Recover a flapping integration

```
1. ha_config_entries op=get entry_id=<…>            # current state
2. ha_config_entries op=reload entry_id=<…>
3. ha_system_log op=list level=ERROR                # see if it recovered
```

---

# Errors, timeouts, and recovery

- Every tool error returns `isError:true` plus a human-readable message.
  Programmatic clients should inspect `content[0].text`.
- Protocol-level errors (malformed JSON-RPC, unknown method) use standard
  JSON-RPC `error` envelopes with codes `-32700` / `-32600` / `-32601`.
- `429 Too Many Requests` from the HTTP layer means the per-token rate
  limit triggered. The `Retry-After` header is set. Default 600 req/min.
- HA restart drops the connection; clients should retry. Idempotent reads
  (`ha_list_states`, `ha_history`) are always safe to repeat.

---

# Where to go next

- **[Developer guide](./developer-guide.md)** — add a tool, run tests,
  understand the request flow.
- **[Release process](./release.md)** — versioning and changelog discipline.
- The README has the install + smoke-test reference card.
