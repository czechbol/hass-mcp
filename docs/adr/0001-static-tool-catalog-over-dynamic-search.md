# Static tool catalog over dynamic tool-search

We expose every tool statically in `tools/list` and shrink the catalog by
consolidating tools and slimming schemas — rather than shipping a tiny catalog
(e.g. `search_tools` / `describe_tool` / `call`) that loads tool schemas on
demand, the BM25-style approach used by projects like `homeassistant-ai/ha-mcp`.

## Context

The `tools/list` payload is a standing tax on every conversation: ~8–12K tokens,
~70% of it in input schemas. A dynamic catalog would cut that to a handful of
schemas — the largest possible win against context pollution.

## Decision

Keep the catalog static. Reduce its weight by: filtering disabled tool classes
out of `tools/list`, deleting redundant tools, merging confusable siblings into
`op`/`kind` meta-tools, and slimming schemas of mechanical bloat.

## Why not dynamic tool-search

- **No native MCP affordance.** MCP has no deferred-tool concept, so a dynamic
  catalog means hand-rolling a meta-protocol the client's model must learn —
  a bespoke search-then-call dance instead of standard tool calling.
- **Client- and model-agnostic is a hard requirement.** This is a HACS
  integration shipped to unknown MCP clients running unknown model tiers.
  ha-mcp's own docs report weaker models stumble on the search indirection;
  we can't pick our users' models.
- **The trade isn't worth it here.** Static consolidation + schema slimming
  recovers a meaningful share of the cost while staying robust and standard.
  The dynamic approach trades that robustness for a token win we don't need
  badly enough.

Revisit if MCP standardizes deferred/lazy tool loading, or if the catalog grows
large enough that static slimming stops being sufficient.
