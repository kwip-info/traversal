# Layer 1 — Rust graph core

Status: planned; implement only after layer 0 is complete.

## Design to finalize before code

- A mutable builder owns dense graph-local IDs and stable caller node names.
- References must carry provenance or otherwise reject foreign-graph handles;
  an index from a different builder must never silently address a local node.
- Validate unique names, dependency references, self-edges, duplicate dependency
  policy, and cycles with actionable offending names.
- Freeze to an immutable adjacency representation with topological order.
- Compute requested targets and their full ancestor closure without executing
  callables. Distinguish selected nodes from unneeded nodes.
- Keep data binding in Python; the core stores dependency kinds/metadata only
  where required by the agreed contract. Do not add scheduler state in this layer.

## Gate tests

Empty and singleton graphs; chain; diamond/shared ancestor; disconnected branches;
multiple targets with overlapping ancestors; self and multi-node cycles; duplicate
names and edges; unknown targets; foreign handles; repeated compilation after
builder changes; long chains without recursive stack overflow. Check topological
invariants against a simple independent reference implementation for generated DAGs.

Record graph sizes and complexity; optimize only from evidence. Update the skill
with implemented capabilities without promising execution. Record final API
choices and test evidence here before marking the layer complete.
