# Local history and recovery

History(path) explicitly creates a SQLite store. Use a local filesystem. Reads do
not infer abandoned work or mutate run status. Run IDs are unique and ordering
uses a database sequence; latest attempt differs from latest successful run.

`history.get(run_id)` returns run metadata and node states. `history.runs(graph=...,
status=..., limit=20)` lists recent records. Before acting on an unfinished run,
inspect its task semantics and external systems if needed. `history.recover(run_id)`
requires the run's OS lease to be free; RunActiveError means a local owner remains.
After process death, running work is unknown, unstarted work is cancelled, and the
run is interrupted. Completed evidence is retained. Unknown does not mean failed.

Default durable errors include only exception types. History(error_formatter=...)
can opt into bounded redacted diagnostics; in-memory reports contain full failures.
No automatic data upload, deletion, cache reuse or replay occurs.

## Explicit result reuse

Cache(key) is a declaration that skipping/repeating the computation is safe and
that the caller maintains its compatibility key. Fingerprints include graph name,
graph version, node name/key and dependency fingerprints. Literal Python inputs
are not automatically hashed: encode their relevant revision in the key. A parent
without a cache declaration disables downstream reuse. Only finite JSON-native
values with string dictionary keys are stored; tuples, custom objects, cycles,
and results above the store's byte limit remain successful but uncached.

`plan.explain_run()` reports run/reuse/unselected decisions without execution.
`plan.explain_run(previous=run_id)` additionally identifies non-repeat-safe work
requiring a decision. `plan.resume(run_id, rerun=[...])` creates a new linked run.
Async callers use `await plan.arun(previous=run_id, rerun=[...])`. Previously
running runs must be explicitly recovered first. A forced rerun names exactly
which tasks to execute; cache compatibility still governs other tasks.

Cached artifacts have integrity checks, not cryptographic authenticity against a
malicious store owner. Keep the database local and trusted. Local metadata and
opted-in results remain until the caller removes the store; no retention daemon.
