# Execution semantics — 0.1.0

Rust owns topology, readiness, capacity and state transitions. Python retains
callables and values. Plan.describe() does not execute tasks. Compilation validates
the whole graph and freezes binding containers; arbitrary objects are not copied.
Caller-supplied unique names are stable logical identities; Node handles are graph-specific.

A run executes only selected targets and their ancestors. Data dependencies bind
arguments; ordering dependencies only wait. A join starts after all required
parents succeed. No retries occur. Each selected task is admitted at most once
within the run. This is not exactly-once execution of external effects across runs.

Ready tasks overlap up to max_concurrency. Independent branches continue after
failure; descendants become blocked. Async cancellation stops admission, requests
cancellation of async functions, and drains blocking threads. It cannot undo work.
A blocking task without its own timeout can delay cancellation indefinitely.

RunReport holds all successful outputs until released, including intermediate
values. This favors inspection over automatic memory reclamation in the first
release. No argument/result serialization is required for local handoff. Functions
must coordinate concurrent mutation themselves. Full traces stay in memory by default. Optional History persists metadata and
Cache persists explicitly declared JSON results; see history.md.
