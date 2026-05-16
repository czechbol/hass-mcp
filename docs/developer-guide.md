# Developer guide

How `hass-mcp` is built, how to add a new tool, and how to run the test
suite. Audience: contributors comfortable with Python + Home Assistant
internals, or LLM-tooling engineers extending the MCP surface.

## Architectural overview

```
                  ┌───────────────────────────────────────────────────────┐
                  │                Home Assistant process                 │
                  │                                                       │
   MCP client ───▶│  HomeAssistantView /api/hass_mcp  (http.py)             │
   (POST JSON-RPC)│        │                                              │
                  │        ▼                                              │
                  │  RateLimiter   ──── 429 if exceeded                   │
                  │        │                                              │
                  │        ▼                                              │
                  │  protocol.dispatch  ───── tools/list, tools/call,     │
                  │        │                  initialize, ping            │
                  │        ▼                                              │
                  │  registry.TOOLS[name].handler(hass, **args)           │
                  │        │                                              │
                  │  ┌─────┴─────────────────────────────────────────┐    │
                  │  ▼                                               ▼    │
                  │  In-process HA APIs                       ws.ws_call  │
                  │  (hass.states, services,                  (mocked     │
                  │  registries, recorder,                     connection │
                  │  loader, …)                                wraps any  │
                  │                                            WS cmd)    │
                  └───────────────────────────────────────────────────────┘
```

Key invariants:

1. **Stateless POST.** Every request is a self-contained JSON-RPC message.
   No persistent connection, no session, no SSE. `initialize` advertises
   `tools: {listChanged: false}` honestly.
2. **Bearer auth via HA.** The view sets `requires_auth = True` so HA's
   middleware vets the `Authorization` header before our handler runs.
   The integration never sees the token directly.
3. **Tools self-register at import.** `tools/__init__.py` imports every
   `tools/*.py` module; each module decorates handlers with `@tool(...)`
   which populates `registry.TOOLS`.
4. **Errors don't escape as protocol failures.** Tool exceptions are wrapped
   into `isError:true` responses with an actionable message. Only genuine
   protocol violations (bad JSON-RPC, unknown method) use the `error`
   envelope.

## Repository layout

```
custom_components/hass_mcp/
  __init__.py        # Integration setup + option propagation
  manifest.json      # HA manifest (deps, after_dependencies, version)
  const.py           # DOMAIN, option keys, defaults, version
  config_flow.py     # UI option form + options flow
  http.py            # HomeAssistantView, rate-limit gate, JSON dispatch
  protocol.py        # JSON-RPC routing (initialize / tools.* / ping)
  registry.py        # @tool decorator, ToolDef, pagination, schema helper
  rate_limit.py      # Sliding-window per-key limiter
  ws.py              # In-process WS command dispatch (mocked connection)
  strings.json       # UI text for config flow
  translations/en.json
  tools/             # One file per tool group, self-registering
    __init__.py      # Import side-effects → registers every tool
    states.py
    services.py
    registries.py
    yaml_config.py
    …
tests/
  conftest.py
  test_rate_limit.py
  test_registry.py
  test_protocol.py
.github/workflows/ci.yml   # hassfest + HACS + ruff + pytest
```

## Request lifecycle

1. **HTTP** — aiohttp routes POST `/api/hass_mcp` to `MCPView.post`. HA's
   auth middleware already approved the bearer.
2. **Rate limit** — `MCPView` keys the limiter on the last 32 chars of the
   `Authorization` header (or `request.remote` if absent). Over the limit
   → `429 Too Many Requests` with `Retry-After`.
3. **Parse JSON-RPC** — single-message or batch. Malformed → `-32700`.
4. **Dispatch** — `protocol.dispatch` routes by method:
   - `initialize` → server info + capabilities.
   - `notifications/initialized` → ack, no response.
   - `ping` → empty result.
   - `tools/list` → emit every `ToolDef.to_listing()`.
   - `tools/call` → check permission gates, run handler.
   - `resources/list`, `prompts/list`, `resources/templates/list` →
     empty list (we don't expose any).
   - Anything else → `-32601 method not found`.
5. **Tool handler** — async function receiving `(hass, **validated_kwargs)`.
   Returns any JSON-serialisable value (typically `dict`).
6. **Response envelope** — `_tool_success` wraps the return value as
   `content: [{ type: "text", text: <json> }]` and (if dict) attaches a
   `structuredContent` mirror. `_json_default` handles `MappingProxyType`,
   `datetime`, `Enum`, `set`, etc.

### Tool error contract

Inside a handler, raise `from ..protocol import ToolError` with a hint
describing the fix:

```python
raise ToolError(f"entity_id '{entity_id}' not found; check ha_list_states")
```

`protocol.py` catches it, your client sees `isError:true` with the
message. For *unexpected* exceptions, the dispatch wraps them as
`{type(e).__name__}: {e}` and logs full traceback to HA's logger.

## How to add a new tool

### 1. Pick the pattern

- **Endpoint-shaped** — one tool per logical action (`ha_render_template`).
- **Meta-tool** — `kind` + `op` parameterized over a related family
  (`ha_registry`, `ha_yaml_config`, `ha_helper`). Preferred when you have
  >2 closely related ops; keeps the tool catalog manageable.

### 2. Create the module

```python
# custom_components/hass_mcp/tools/my_thing.py
"""ha_my_thing — short description."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from ..protocol import ToolError
from ..registry import LIMIT_FIELD, OFFSET_FIELD, paginate, schema, tool


_OPS = ("list", "get")


@tool(
    name="ha_my_thing",
    description=(
        "One sentence that tells the agent WHEN to use this tool and "
        "what arguments matter. The agent reads only this — be specific."
    ),
    input_schema=schema(
        properties={
            "op": {"type": "string", "enum": list(_OPS)},
            "id": {"type": "string"},
            "limit": LIMIT_FIELD,
            "offset": OFFSET_FIELD,
        },
        required=["op"],
    ),
    read_only=True,                # mutating? → False
    # requires_write=True,          # → gated by allow_write
    # requires_destructive=True,    # → gated by allow_destructive
    # requires_fire_event=True,     # → gated by allow_fire_event
)
async def ha_my_thing(
    hass: HomeAssistant,
    op: str,
    id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if op not in _OPS:
        raise ToolError(f"unknown op '{op}'")
    if op == "list":
        items = [...]
        return paginate(items, limit, offset)
    if op == "get":
        if not id:
            raise ToolError("op=get requires id")
        return {...}
    raise ToolError(f"unsupported op '{op}'")
```

### 3. Register the module

```python
# custom_components/hass_mcp/tools/__init__.py
from . import (  # noqa: F401
    ...,
    my_thing,
)
```

### 4. Document and version

- Add a row in `README.md`'s tool table.
- Add a row in `docs/user-guide.md`.
- `## [Unreleased]` → `### Added` line in `CHANGELOG.md`.
- Bump `manifest.json` version + `const.SERVER_VERSION`.

### 5. Test

For pure logic, add a unit test under `tests/`. For tool-handler tests
that need `hass`, use a `MagicMock`:

```python
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def hass():
    m = MagicMock()
    m.data = {"hass_mcp": {"options": {}}}
    return m

@pytest.mark.asyncio
async def test_my_thing(hass):
    from custom_components.hass_mcp.tools.my_thing import ha_my_thing
    result = await ha_my_thing(hass, op="list")
    assert result["total"] == 0
```

We deliberately avoid the real `pytest-homeassistant-custom-component`
fixtures for unit tests — they're heavy and our handlers don't need a
full hass.

## Calling WebSocket-only HA features

Many HA features (helpers CRUD, backup, lovelace, HACS, system_log, auth)
have no in-process Python API — only WebSocket commands. Use `ws.ws_call`:

```python
from ..ws import WsCallError, ws_call

try:
    result = await ws_call(hass, "backup/info")
except WsCallError as e:
    raise ToolError(str(e)) from e
```

What `ws_call` does:

- Looks up the registered handler in `hass.data["websocket_api"]`.
- Validates the message via the handler's voluptuous schema (treats HA's
  `_ws_schema=False` "no-args" marker as no validation).
- Builds a fake `ActiveConnection` with the first available admin user, so
  `@require_admin` handlers don't reject the call.
- Captures `send_result` / `send_error` / `send_message` into a future.
- Unwraps `{type: "result", result: ...}` envelopes.

When you need to add a tool that wraps a WS command:

1. Find the command name in HA core or the integration source (search for
   `vol.Required("type"): "..."`).
2. Watch out for inconsistent param names (e.g. HACS uses both `repository`
   and `repository_id` across its commands).
3. If the command streams (e.g. `backup/subscribe_events`), `ws_call`
   captures only the first message — use the canonical Python API instead.

## Style and discipline

- **Schemas** are JSON Schema dicts (not Pydantic) — keeps dependencies
  light and matches what `tools/list` emits.
- **Tool descriptions** are the agent's only hint. State the WHEN, not the
  WHAT. Mention required args inline.
- **Error messages** name the next step (`use ha_list_services`, `check
  ha_registry kind=area`). The model reads them, you reduce its trial loop.
- **Logging** — every `tools/call` logs at INFO with the tool name and
  capability class. Tool handlers should log warnings/errors as usual but
  never swallow them silently.
- **Imports** must satisfy ruff `I` (sorted) and `F` (no unused). Run
  `ruff check .` before pushing.

## Running checks locally

```sh
ruff check .
ruff format --check .
pytest -v
```

`hassfest` and `hacs/action` only run in CI (they're Docker-based and slow
to bootstrap locally) — see [.github/workflows/ci.yml](../.github/workflows/ci.yml).

## Common pitfalls

- **Forgetting to bump the version.** HA caches custom integrations by
  version string; without a bump, HACS update + HA restart loads stale
  bytecode and you'll waste 10 minutes wondering why the fix didn't take.
- **Importing HA components at module top.** Some integrations (`recorder`,
  `logbook`) take a noticeable time to import. Lazy-import inside the
  handler.
- **Returning HA objects directly.** `Mapping`/`MappingProxyType`,
  `Enum`, `datetime`, `set` need either explicit conversion or the JSON
  encoder defined in `http._json_default`. When in doubt, build a plain
  `dict` from primitives.
- **Bypassing the permission gate.** Don't catch `ToolError` and convert
  to success — the gate is the user's only safeguard against an agent
  running wild.

## Where to ask

GitHub issues: <https://github.com/czechbol/hass-mcp/issues>.
