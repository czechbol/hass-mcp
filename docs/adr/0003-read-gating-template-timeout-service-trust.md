# Admin-gate sensitive reads; bound template renders; document service-call trust

Three decisions from the post-2.1.0 security validation (the 4-agent review).
Recorded together because they share one theme: where the two-layer permission
model (server policy + effective user) needed extending beyond *mutations*.

## Decision 1 (was F-002): admin-gate the secret/PII/location-bearing reads

**Context.** The permission model gated only mutations, so any authenticated
token — including a non-admin one — could call read tools that expose data HA
itself treats as admin-only.

**Decision (option A of two).** Require the effective user to be an admin for the
specific reads that leak secrets, credentials, or precise location — and *only*
those. Implemented via a new per-op `admin_ops` set on `@tool`, enforced
centrally in `_tools_call` regardless of read/write, requiring both a present
user and `is_admin`.

Gated: `ha_system op=read_error_log` / `read_system_log` / `get_config`;
`ha_config_entries op=list/get`; all `ha_diagnostics` ops.

**Explicitly left open** (option B rejected): `ha_registry` listing, `ha_trace`,
`ha_backup` info, `ha_hacs` info, `ha_config_flow` listing, `ha_system
check_config/get_health`, and all core monitoring reads (states, history,
statistics, templates, lovelace). These are setup *information*, not secrets.

**Why A over B.** A preserves a supported "hand out a non-admin read-only
monitoring token" story — state/history/inventory stay observable — while
closing the actual disclosures (secrets in logs, credentials in diagnostics,
integration configs, exact GPS). B (gate everything HA's admin panels gate)
would make a non-admin token nearly blind for a marginal confidentiality gain,
and some of its extra ops (registry listing) aren't even admin-only in HA.

## Decision 2 (was F-007): bound `ha_render_template` execution, keep power

**Context.** `ha_render_template` runs a full (`limited=False`) Jinja render
synchronously in the event loop with no time bound — a runaway template
(`{{ range(10**8)|sum }}`) blocks all of Home Assistant.

**Decision (option A).** Keep `limited=False` as the default — the powerful
whole-state query is the tool's purpose — but bound execution with HA's own
`Template.async_render_will_timeout(timeout)` as a pre-flight guard; reject with
a `ToolError` if the template would exceed the budget. No admin gate (it's a
read; secrets exposure is covered by the token's own reach).

**Why A over "default limited=True".** `limited=True` materially degrades the
tool for agents (the point is cross-entity queries). The timeout removes the DoS
without removing the capability.

## Decision 3 (was whitebox #3): document the service-call trust assumption

**Context.** `ha_call_service` passes `Context(user_id=…)` for attribution, but
`hass.services.async_call` does not enforce per-user entity permissions — so a
write-enabled non-admin token can call any service.

**Decision (option A).** Leave the behavior; document it. This matches Home
Assistant's own default (non-admins can call services). Making it admin-only
would be stricter than HA and break the common "let the agent control devices
with a non-admin token" use case. The `requires_admin` layer already covers the
operations HA itself treats as admin-only.

**Post-validation note.** A later re-review claimed this *bypassed* HA's
per-entity permission check. Verified false against HA source: `ha_call_service`
passes `Context(user_id=…)`, and HA's shared `entity_service_call`
(`helpers/service.py`) runs `user.permissions.check_entity(entity_id,
POLICY_CONTROL)` for any non-admin context — so a restricted non-admin **is**
blocked, identically to HA's own WS/REST path. This is genuinely equivalent to
HA, not merely an accepted risk.
