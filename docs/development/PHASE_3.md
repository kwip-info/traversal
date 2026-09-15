# Layer 3 — Python graph execution

Status: complete. Layers 1–2 complete.

Public API: Graph(name, version='1'), add(name, function, *args, after=(), **kwargs),
depends_on(node, *dependencies), compile(*targets), run(*targets, max_concurrency=4),
Plan.describe(), Plan.run(), await Plan.arun(). Node references in built-in lists,
tuples and dictionary values supply data; `after` adds ordering only. Arbitrary
objects remain opaque references. Explicit targets are required.

The compiled topology lives in Rust. Python freezes task definitions and bindings
and submits only admitted work. Async functions run on the caller's event loop;
blocking functions use a run-owned thread pool with copied context variables.
RunReport provides states, outputs and structured failures; raise_for_status is
explicit. Cancelling arun stops admission, cancels async nodes cooperatively, drains
running threads, and re-raises cancellation. No process executor or retry yet.

Gate tests use barriers/events, not duration thresholds: branches overlap, an early
child starts before an unrelated branch finishes, joins wait, capacity is enforced,
errors block descendants, foreign references fail, plans survive builder mutation,
nested bindings resolve, and cancellation drains threads. Build and test wheels.

## Evidence

15 Python tests pass on macOS arm64 CPython 3.14.5; Rust 11 tests pass.
Read-only Git audit successfully joined Traversal and kwip.info repository results.
Initial invocation had a wrong example path; corrected input and verified success.
Median of seven 101-node runs (100 tasks sleeping 1 ms, concurrency 4): direct
Python thread pool 31.87 ms, Traversal 41.06 ms, below preselected 83.74 ms budget.
This demonstrates acceptable small-workflow overhead, not a speed advantage.
The skill now teaches PyPI setup and a tested branching example; CLI exports it.
