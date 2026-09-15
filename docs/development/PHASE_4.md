# Layer 4 — durable local history

Status: complete. Layers 1–3 complete.

Use Python's standard sqlite3 adapter for opt-in metadata storage; Rust remains
responsible for graph/scheduler state. History(path) initializes a versioned SQLite
WAL database with short FULL-synchronous transactions. Graph(..., store=history)
records run identity, graph version, task start/outcome, and final states. Payloads
are not persisted. Default durable error text is exception type only; an explicit
formatter can supply bounded redacted diagnostics.

Each active run holds an OS advisory lock in an adjacent locks directory (flock
on Unix, msvcrt locking on Windows). History reads never recover runs. Explicit
recover(run_id) must acquire the lease; otherwise it raises RunActiveError. After
process death, running nodes become unknown; unstarted nodes become cancelled;
the run becomes interrupted. Completed evidence remains. Run ordering uses SQLite
sequence IDs rather than wall-clock timestamps. Metadata/state is process-safe;
network filesystems and remote/shared multi-host stores are outside support.

Gate: latest attempt/success ordering, no implicit recovery, two store instances,
live recovery rejection, subprocess kill/recovery, schema-version rejection,
redaction, failed writes before invocation, and unchanged in-memory execution.

Evidence: 21 Python tests pass, including live-lease rejection and a real killed
subprocess. The running task becomes unknown only after explicit recovery.
Default payload/error-message non-persistence, independent connections, invalid
schemas, and failure-before-task-invocation pass. Format/lint pass.
