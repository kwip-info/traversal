# Layer 2 — execution state

Status: complete. Layer 1 complete.

Rust owns per-run state, ready queue, unresolved counters, and positive capacity.
States: unselected, pending, ready, running, succeeded, failed, blocked, cancelled.
Admission returns a batch up to available capacity; completion is valid only for
running nodes. Failure blocks descendants and independent branches continue.
Cancellation marks unstarted work cancelled and lets adapters drain running work.
Ready entries invalidated by cancellation/failure are skipped lazily. No retry.

Gate: both diamond completion permutations; wide graph capacity; invalid and
repeated completion; independent failure; cancellation while work is active;
unselected branches never admitted; empty targets and zero capacity rejected.
Execution remains Python-independent. No timer, polling, thread pool, or runtime
is embedded in the Rust core; Python adapters deliver completion events later.

Evidence: 11 Rust tests pass (6 topology, 5 state); Rust format and clippy pass.
Completion and cancellation do not scan the graph during ordinary successful
completion; cancellation scans states once. Scheduler has no Python dependency.
