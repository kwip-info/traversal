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
