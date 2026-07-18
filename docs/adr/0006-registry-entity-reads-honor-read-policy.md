# `ha_registry` entity reads honor per-entity read policy

`ha_registry` `kind=entity` `list`/`get` now filter by the token owner's
`POLICY_READ`, closing the last read path that leaked entity data to a
restricted non-admin token. Revises ADR-0004, which lumped `ha_registry` under
"inventory stays open" and so missed the entity-registry case.

## Context

ADR-0004 set out the goal that "a restricted non-admin token now observes only
its permitted entities across all read tools," filtering the entity-data reads
(`ha_list_states`, `ha_get_state`, `ha_describe_entity`, `ha_search`,
`ha_camera_snapshot`, `ha_history`, `ha_render_template`) and masking
single-entity reads as not-found "so there is no existence oracle." ADR-0005
extended that to `ha_statistics` and `ha_trace`.

ADR-0004 explicitly left "device/area/label *inventory* (`ha_search` non-entity
kinds, `ha_registry`) open, consistent with ADR-0003's line between setup
information and entity data." But `ha_registry` also serves `kind=entity`, which
is not inventory — it is per-entity data. `requires_admin=True` on the tool gates
only mutations (`_tools_call`'s `mutating and requires_admin`), so the read ops
were callable by any authenticated token with no per-entity check:

- `kind=entity op=list` returned the **entire** entity registry — every
  `entity_id`, `unique_id`, `platform`, `device_id`, `area_id`, `name`,
  `options` — including entities the token's policy hides.
- `kind=entity op=get` returned a hidden entity's registry entry, a direct
  existence oracle for exactly the entities `ha_get_state` masks. Same class of
  data, unfiltered — the gap ADR-0005 closed for statistics and trace.

## Decision

Apply the effective user's `POLICY_READ` to `_entity_ops`, mirroring
`ha_list_states` / `ha_get_state`:

- **Filter** `op=list` result rows by `can_read_entity(e.entity_id)`.
- **Mask as not-found** `op=get` when `not can_read_entity(id)`, using the same
  message as the missing-entry case so there is no existence oracle.

Both are skipped when `can_read_all_entities()` — admins, the owner, and
full-access non-admin users are unaffected.

Device / area / label / floor registries remain open, unchanged: ADR-0004's
inventory-vs-entity-data line still holds for those kinds. Only `kind=entity` is
entity data and so newly scoped.

## Consequences

- The last read path that ignored the per-entity read policy now respects it;
  the read side is fully consistent with ADR-0004's stated goal.
- No change for admins, the owner, or the common full-access non-admin token.
- Ships in 2.2.2 (`Security`). Tool names and schemas unchanged.
