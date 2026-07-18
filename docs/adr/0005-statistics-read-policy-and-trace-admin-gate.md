# Filter statistics reads by per-entity policy; admin-gate trace

Two read-path corrections found while auditing 2.2.0's per-entity read
enforcement for completeness. Both close gaps between the stated model and its
actual coverage. Revises ADR-0004 (which missed `ha_statistics`) and ADR-0003
Decision 1 (which explicitly left `ha_trace` open).

## Decision 1: `ha_statistics` reads honor `POLICY_READ`

**Context.** ADR-0004 filtered the read tools that expose entity data
(`ha_list_states`, `ha_get_state`, `ha_describe_entity`, `ha_search`,
`ha_camera_snapshot`, `ha_history`, `ha_render_template`) by the token owner's
per-entity read policy — stating the goal that "a restricted non-admin token
now observes only its permitted entities across all read tools." `ha_statistics`
was not in that sweep. Its `requires_admin=True` gates only the mutating `clear`
op (per `_tools_call`'s `mutating and requires_admin`), so the read ops
`list_ids` / `period` / `metadata` were callable by any authenticated token with
no per-entity check. A restricted token blocked from `ha_history` on
`sensor.bedroom_power` could still read its long-term values via
`ha_statistics op=period` — the same class of data, unfiltered.

**Decision.** Apply the effective user's `POLICY_READ` to statistics reads,
mirroring `ha_history`: drop `statistic_ids` (and `list_ids` result rows) the
user may not read, short-circuiting to an empty result when nothing remains.
Recorder statistics for a tracked entity use the entity_id verbatim as the id,
so `can_read_entity(sid)` applies directly. External statistics use a
`source:object` form with no HA entity — those pass through unchanged (there is
no `POLICY_READ` to apply). Admins/owner/full-access users are unaffected.

**Note vs. native HA.** HA's own statistics WS commands
(`recorder/list_statistic_ids`, `.../statistics_during_period`,
`.../get_statistics_metadata`) are **not** admin-gated and do **not** apply
per-entity read policy — verified against HA source. This decision is therefore
*stricter* than HA baseline, deliberately, to keep the integration's per-entity
read model internally consistent (ADR-0004).

## Decision 2: `ha_trace` is admin-only (all ops)

**Context.** ADR-0003 Decision 1 (option A) explicitly left `ha_trace` open as
"setup information, not secrets." That predates ADR-0004's tighter line: traces
embed entity **values** (trigger data, `this`, `changed_variables`) plus full
automation/script logic. So a restricted non-admin token could read entity data
through traces that ADR-0004 blocks everywhere else — and HA's own trace WS
commands (`trace/get`, `trace/list`, `trace/contexts`) are all
`@websocket_api.require_admin` (verified against HA source).

**Decision.** Gate every `ha_trace` op behind an admin token via
`admin_ops=["list", "get", "contexts"]`, enforced centrally in `_tools_call`.
This matches HA's native gating and removes the entity-data leak. A non-admin
token is refused rather than given filtered traces — trace payloads are
free-form and can't be reliably scrubbed per-entity, the same reasoning
ADR-0004 applied to `ha_render_template`.

**Why reverse ADR-0003 D1 here.** The original "leave open" call weighed a
non-admin monitoring token's convenience against disclosure. ADR-0004 already
resolved that tension for entity data in favor of enforcement; trace is squarely
entity data, and native HA agrees it is admin-only. Consistency wins.

## Consequences

- Ships as 2.2.1, `Security`. Tool names/schemas unchanged.
- A restricted non-admin token can no longer read statistics for hidden entities
  or read any automation/script trace.
- No change for admins, the owner, or the common full-access non-admin token.
