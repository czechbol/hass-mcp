# Native MCP for Home Assistant

An HA custom integration that mounts an MCP server inside Home Assistant,
exposing a small set of generic `ha_*` meta-tools over the full HA admin
surface. This glossary fixes the vocabulary those tools share.

## Language

**Meta-tool**:
A single `ha_*` tool that covers a whole capability area through a discriminator
argument, rather than one tool per action. The deliberate alternative to
exposing dozens of narrow tools.
_Avoid_: command, endpoint

**op**:
The action-verb discriminator on a meta-tool (`list`, `get`, `create`,
`delete`, …). Always a verb. Every meta-tool that dispatches on an action uses
`op` and nothing else for that axis.
_Avoid_: mode, action, operation, type

**kind**:
The resource-type discriminator, added *only* when one meta-tool spans several
resource types (e.g. `input_boolean` vs `counter` vs `timer`; `state_changes`
vs `logbook`). Answers "what is being acted on", while `op` answers "what to
do". A tool with a single resource type has no `kind`.
_Avoid_: type, category, resource

**Tool class**:
The permission category an action falls into — read, write, destructive, or
fire-event. For a meta-tool the class is decided **per `op`** (e.g. `delete` is
destructive while `list` is read), not per whole tool. The integration options
decide which classes are enabled at all.
_Avoid_: permission group, scope

**Server policy**:
The admin-configured layer that decides which tool classes this MCP endpoint
may perform at all (`allow_write` / `allow_destructive` / `allow_fire_event`).
Applies to every caller, including admins. Distinct from — and checked before —
the caller's own identity.
_Avoid_: global permission, master switch

**Effective user**:
The Home Assistant user a tool call executes as — the owner of the bearer token
that made the request — whose own permissions Home Assistant enforces. Never a
substitute admin.
_Avoid_: service account, system user
