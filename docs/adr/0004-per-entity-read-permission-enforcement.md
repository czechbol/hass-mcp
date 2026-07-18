# Enforce per-entity read permissions on read tools

Read tools filter their results by the token owner's Home Assistant per-entity
read policy (`POLICY_READ`), mirroring what the write path already gets from
HA's `entity_service_call`. Revises ADR-0003 Decisions 1 and 2, which left core
monitoring reads (state, history, templates) open to any authenticated token.

## Context

ADR-0002 made every call execute as the token owner, and ADR-0003 Decision 3
verified that `ha_call_service` therefore honors the owner's per-entity
*control* policy — HA's shared `entity_service_call` runs
`check_entity(entity_id, POLICY_CONTROL)` for a non-admin context.

The read path had no equivalent. `ha_list_states`, `ha_get_state`,
`ha_describe_entity`, `ha_search`, `ha_camera_snapshot`, `ha_history`, and
`ha_render_template` all read from `hass.states` (or the recorder) directly,
with no per-user filtering. So a **restricted non-admin token** — the exact
"read-only monitoring token" ADR-0003 Decision 1 set out to preserve — could
read *every* entity in the install, including ones its HA policy hides
(`device_tracker` location, cameras, sensors). Native HA's WS `get_states`
filters these by `check_entity(..., POLICY_READ)`; the integration bypassed it.

This is an asymmetry, not a new attacker: writes respected the owner's policy,
reads did not.

## Decision

Add `can_read_entity(entity_id)` and `can_read_all_entities()` to `identity.py`,
resolving the effective user's `permissions.check_entity` /
`access_all_entities` against `POLICY_READ`. Admins, the owner, and default
full-access users pass unchanged; no user in context (direct unit-test call)
passes, since `requires_auth=True` guarantees a user on every real request.

Apply them in the read handlers:

- **Filter** result sets — `ha_list_states`, `ha_search` (entity results),
  `ha_history` (`entity_ids`).
- **Mask as not-found** single-entity reads the user can't see —
  `ha_get_state`, `ha_describe_entity`, `ha_camera_snapshot` — so there is no
  existence oracle.
- **Gate** `ha_render_template` on `can_read_all_entities()`: a template reads
  state through a channel we can't filter per-entity, so a restricted user is
  refused rather than given a partial-but-leaky render. This supersedes
  ADR-0003 Decision 2's "no admin gate" for the restricted case only — the
  powerful `limited=False` default and the timeout guard are unchanged for
  users with full read access.
- `ha_history` logbook can't filter `device_ids` per-entity, so a restricted
  user must scope by `entity_id`.

Device/area/label *inventory* (`ha_search` non-entity kinds, `ha_registry`)
stays open, consistent with ADR-0003 Decision 1's line between setup
information and entity data.

## Consequences

- A restricted non-admin token now observes only its permitted entities across
  all read tools — the read side finally matches the write side and native HA.
- No change for admins, the owner, or the common default non-admin user (whose
  policy already grants all entities), so the "hand out a monitoring token"
  story is preserved *and* now actually scoped.
- Tool names and schemas are unchanged; ships as a minor + `Security` release
  (2.2.0), same shape as the ADR-0002 write-side change.
