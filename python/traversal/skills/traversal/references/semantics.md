# Intended semantics — not yet implemented

Traversal is an in-process DAG library. Rust owns graph structure, target closure,
readiness, admission limits, and state transitions. Python retains callables and
values and invokes work through appropriate execution adapters. No serialization
is needed merely to pass a value between local nodes.

Ready nodes can overlap up to the run's concurrency limit. Completion releases
only direct dependents; a join waits for every required dependency. Stable node
names identify logical work; run IDs distinguish attempts. Graphs are frozen
before a run. Python CPU parallelism is not implied by a Rust scheduler.

History records outcomes; caching additionally persists results and requires
explicit compatibility keys. Success alone does not establish reusability.
An interrupted external call may have an unknown outcome. Traversal cannot
provide exactly-once external effects or forcibly stop arbitrary running threads.

Calendar scheduling, connectors, distributed execution, dashboards, and task
business logic are outside the component. The current package implements none
of these planned graph semantics; consult the matching version's skill before use.

Development milestone: Rust topology validation and target selection now pass
layer 1 tests. These are internal Rust capabilities; no Python graph API exists yet.

Layer 2 Rust readiness, capacity, completion and cancellation state now pass
controlled tests. Python execution remains unavailable until layer 3.
