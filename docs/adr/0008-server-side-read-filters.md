# Server-side read filters for registry listing and the error log

`ha_registry kind=entity op=list` gains `device_id` / `config_entry_id` /
`area_id` filters, and `ha_system op=read_error_log` gains `head` and `contains`.
Both narrow a large read at the source instead of returning the whole payload for
the client to post-process.

## Context

Two reads routinely overran the tool-result token budget and forced out-of-band
workarounds (dumping to a file and running `jq` / `grep`):

- `ha_registry kind=entity op=list` returned the entire entity registry (~1400
  rows, ~85 KB on one install). There was no way to ask for just one device's or
  one integration's entities — the `id` argument is only wired to
  `get`/`update`/`delete`, so passing a device id to `list` silently returned
  everything.
- `ha_system op=read_error_log` only tailed the last N lines. A log line earlier
  than the tail window (e.g. an integration's boot-time startup message) was
  unreachable, and there was no way to grep for a substring without pulling the
  whole tail back and filtering client-side.

This is the standing concern of ADR-0001: the catalog is kept static and lean
precisely because context pollution is the dominant cost. A read that can only
return everything pushes that cost onto every call.

## Decision

Filter at the source, reusing existing arguments so the schema barely grows:

- **Registry list.** In the `kind=entity op=list` branch, apply `device_id`,
  `config_entry_id`, and `area_id` from `data` as plain equality filters on the
  registry entries before pagination. `data` already exists (it carries
  create/update fields); overloading it for list filters adds no new top-level
  schema property. The per-entity `POLICY_READ` filter from ADR-0006 still runs
  last, so a restricted token's filtered list is also policy-scoped — the new
  filters never widen what a token can see.
- **Error log.** Add `head` (read the first N lines) and `contains` (a
  case-insensitive substring grep over the whole file). When either is set the
  handler reads the full file once in the executor and slices head/tail of the
  matches; the default path (no `head`, no `contains`) keeps the original
  efficient block-wise tail unchanged. `read_error_log` is already admin-only
  (ADR-0003 Decision 1), so no new permission surface is involved.

## Consequences

- Both reads can be scoped before they hit the token budget; the registry dump
  and the boot-time-log lookups that needed SSH + `jq`/`grep` are now first-class.
- No new tools, ops, or permission classes. Tool names are unchanged; the only
  schema additions are optional `head` / `contains` on `ha_system` and three
  documented `data` keys on registry list. Ships as a minor, 2.3.0.
- `data`-as-filter is a small overload of a create/update argument. Acceptable
  here (it keeps the schema lean per ADR-0001) and documented in the `data`
  description and the user guide; if more list filters accrue across kinds, a
  dedicated `filter` object would be the cleaner next step.
