# `ha_webhook` is admin-only

`ha_webhook` now gates its `list` op behind an admin token via `admin_ops`,
closing the last sensitive read left open after the read-path sweep of ADR-0004
through ADR-0006. Implements the non-blocking follow-up frenck raised when
approving the HACS default-catalog submission (hacs/default#7697).

## Context

In the HACS default-repo review, the approving maintainer noted that
`ha_webhook`'s list op returns webhook URLs — which are bearer-equivalent
secrets: anyone holding a webhook URL can POST to the automation behind it — as
a plain read with no admin gate, and suggested treating it the same way the
config-entry reads are treated (ADR-0003 Decision 1).

`ha_webhook` was `read_only=True` with no gating, so any authenticated token,
including a restricted non-admin "monitoring" token, could enumerate every
webhook URL in the install. This is the same class of disclosure ADR-0003 D1
closed for secret/credential-bearing reads and ADR-0005 closed for trace.

## Decision

Gate the op behind an admin token with `admin_ops=["list"]`, enforced centrally
in `protocol.py` `_tools_call` — the same mechanism used for `ha_trace` and the
`ha_config_entries` reads.

This required giving `ha_webhook` an explicit `op` argument. The central gate
reads the op from the raw call args (`op = args.get("op")`) and the
`admin_required` check only fires for a read tool through its `admin_ops` clause
(the `mutating and requires_admin` clause is dead for a read). A single-purpose
tool with no `op` arg therefore could not be gated. The `op` is declared
**required with no Python default** (enum `["list"]`), mirroring `ha_trace`:
omitting it is a client error rather than a silent default that would bypass the
gate.

`requires_admin` was **not** used — on an existing tool it only gates mutations
(`mutating and requires_admin`), and this is a read.

## Consequences

- A restricted non-admin token can no longer list webhook URLs; an admin token is
  unaffected.
- Minor contract change: `ha_webhook` now takes a required `op: "list"` argument.
  The tool is otherwise unchanged.
- Ships in 2.2.3 (`Security`).
