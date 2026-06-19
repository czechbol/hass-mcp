# Quick start

This guide takes you from zero to a Home Assistant administered through an
LLM in under five minutes.

You will need:

- A Home Assistant install you can reach over HTTPS.
- An MCP-capable client (Claude Code, Claude Desktop, Cursor, Continue, or
  anything that speaks the [Model Context Protocol](https://modelcontextprotocol.io/)).
- About four lines of configuration on the client side.

## 1. Install the integration via HACS

1. Open **HACS** in Home Assistant.
2. Top-right menu → **Custom repositories**.
3. Add `https://github.com/czechbol/hass-mcp` as category **Integration**.
4. Search HACS for **Native MCP for Home Assistant** → **Download** → **Restart Home Assistant**.

## 2. Add the integration and choose permissions

After the restart:

1. **Settings → Devices & Services → Add Integration → Native MCP for Home Assistant**.
2. Pick the three permission toggles:

   | Option | Default | Enables |
   |---|---|---|
   | `allow_write` | ✅ on | `ha_call_service`, `ha_set_state`, `ha_yaml_config`, registry updates, helper CRUD, config entry mutations, `ha_assist` |
   | `allow_destructive` | ❌ off | `ha_delete_state`, registry deletes, `ha_recorder purge`, `ha_auth delete_refresh_token` |
   | `allow_fire_event` | ❌ off | `ha_fire_event` |

3. (Optional) `rate_limit_per_minute` — defaults to 600 req/min per token; set
   to 0 to disable.

You can change these later via **Configure** on the integration card.

## 3. Mint a long-lived access token

**Profile → Security → Long-Lived Access Tokens → Create Token**. Name it
something like `mcp-claude-code`. Copy the token immediately — Home Assistant
never shows it again. Treat it like a root password; it grants administrator
access.

## 4. Wire up an MCP client

### Claude Code (recommended)

```sh
claude mcp add homeassistant \
  https://YOUR_HA:8123/api/hass_mcp \
  --transport http \
  --header "Authorization: Bearer YOUR_LONG_LIVED_TOKEN"
```

Or with `--scope user` for a global registration. Verify:

```sh
claude mcp list
```

### Claude Desktop, Cursor, Continue, anything that speaks streamable HTTP

```json
{
  "mcpServers": {
    "homeassistant": {
      "type": "http",
      "url": "https://YOUR_HA:8123/api/hass_mcp",
      "headers": { "Authorization": "Bearer YOUR_LONG_LIVED_TOKEN" }
    }
  }
}
```

### stdio-only client (some IDE extensions)

Wrap the HTTP endpoint with [`mcp-remote`](https://github.com/geelen/mcp-remote):

```json
{
  "homeassistant": {
    "command": "npx",
    "args": [
      "-y", "mcp-remote",
      "https://YOUR_HA:8123/api/hass_mcp",
      "--header", "Authorization: Bearer YOUR_LONG_LIVED_TOKEN"
    ]
  }
}
```

## 5. Smoke-test the endpoint

```sh
curl -sS -X POST https://YOUR_HA:8123/api/hass_mcp \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | jq '.result.tools | length'
```

Expected output: `28` on a default install (tools whose permission class is
disabled aren't listed; enabling `allow_destructive` / `allow_fire_event` adds
more). The exact count varies by version and enabled options.

If you get `401 Unauthorized` the token is wrong. `404 Not Found` means the
integration isn't loaded — check that the config-entry exists and HA was
restarted after the HACS install.

## 6. First real task

In your MCP-aware chat, try:

> Find every light that's currently on and turn off any with brightness above 50%.

The model will discover lights via `ha_list_states`, inspect each with
`ha_get_state`, and call `ha_call_service light.turn_off` on the matches.

If you want to see what the model is doing, ask it to explain the calls
first, or watch HA's `home-assistant.log` — every MCP tool call logs a line
like `hass_mcp tools/call ha_call_service [write]`.

## Next steps

- **[User guide](./user-guide.md)** — every tool, what it does, real
  example calls.
- **[Developer guide](./developer-guide.md)** — add a new tool, run tests,
  understand the request flow.
- **[Release process](./release.md)** — how versions, tags, and the
  CHANGELOG are managed.
