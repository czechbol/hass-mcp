# Execute tool calls as the token owner, gate per-op

Tool calls run with the permissions of the **user who owns the calling bearer
token**, and each meta-tool `op` is gated by its own permission class (read /
write / destructive) — not by a single whole-tool flag, and not as a
substituted admin.

## Context

The original design ran every WebSocket-backed tool call as `admins[0]` (a
hard-coded active admin) on the rationale that HA bearer auth on the endpoint
already gated access — "if you hold a token, you're trusted." Separately,
meta-tools declared a single tool-level `requires_write` / `requires_destructive`
flag (or none), which fit poorly: an `op`-dispatch tool has read, write, and
destructive ops behind one name, so a single flag either under-gated
(`ha_registry` had no flag, so `delete` ran with every safety toggle off) or
over-gated (`ha_recorder` required the destructive toggle even for `op=info`).

A HACS review flagged both: destructive ops bypassing the safety toggles, and
non-admin tokens being elevated to admin.

## Decision

Two independent authorization layers, both enforced on every mutating call:

1. **Server policy** — the admin-configured `allow_write` / `allow_destructive`
   / `allow_fire_event` toggles, gating even admin tokens. Enforced per-`op`
   via declarative `write_ops` / `destructive_ops` on the tool definition,
   checked centrally before the handler runs.
2. **Effective user** — the call executes as the token's owner. `ws_call` sets
   the real user on the connection (the `admins[0]` fallback is removed) and
   service calls pass `Context(user_id=…)`, so Home Assistant's own permission
   machinery enforces the caller's rights. Mutating operations fail closed if
   no user is present.

## Consequences

- Non-admin tokens can no longer perform admin-only actions — a behavior change
  for anyone who relied on the old elevation.
- Destructive ops now require `allow_destructive` (default off); workflows that
  deleted/purged/restored under `allow_write` alone will get a `ToolError`
  until the toggle is enabled.
- The MCP tool contract (names, schemas) is unchanged, so this ships as a
  minor + `Security` release, not a new major.
