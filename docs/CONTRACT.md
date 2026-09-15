# Traversal execution contract

Status: layers 1–6 plus 0.2.0 free-threading qualification. Owner: Trevor Ewert / KWIP LLC.

## Scope

An embeddable Python library with a Rust core for static DAGs, concurrent node
execution, compact local run history, and explicit result reuse. Ordinary Python
owns tasks. Rust owns graph structure and scheduler state. Python adapters own
callable invocation and result references. No hosted component, automatic
telemetry, calendar scheduler, connector catalog, distributed workers, or UI.

## Structure and execution

- Caller-supplied unique nonempty node names remain stable across runs. Internal
  dense IDs are graph-local and cannot substitute for logical identity.
- Compilation validates references and rejects cycles, then freezes topology.
  A run selects the ancestor closure of its requested outputs. Unneeded nodes do
  not execute. An explicit target is required; an empty graph may be inspected.
- Data dependencies and ordering-only dependencies are distinct. Both constrain
  readiness; only data dependencies supply function arguments.
- A node becomes ready only after all required dependencies succeed (including
  explicitly accepted reused results).
- Admission moves ready nodes to running at most once per attempt and never
  exceeds a positive concurrency limit. Automatic retries are off initially.
- A completion updates direct dependents, without scanning the entire graph.
  Ready-node ordering is deterministic for the same event sequence; concurrent
  completion order and side-effect order are not globally deterministic.
- Python objects stay in process by reference. Callers must avoid concurrent
  mutation of shared values; Traversal does not deep-copy or make objects immutable.
- The initial failure policy continues independent branches and blocks descendants
  of failed nodes. Reports distinguish failure from blocked/cancelled work.
- Cancellation stops new admission. Async cancellation is cooperative; running
  threads may finish and perform effects. Never report a running thread as stopped.
- Python exceptions retain meaningful source traceback information. Internal
  invalid transitions return errors; they must not corrupt dependency counts.
- Regular CPython retains the GIL for Python task bodies. Free-threaded CPython
  3.14t can run independent synchronous Python tasks on multiple cores when the
  GIL remains disabled. Async CPU work still blocks its event loop. Process
  executors are deferred.
- A compiled Plan supports concurrent runs with independent scheduler state,
  outputs, failures, and copied contextvars. Construct Graphs on one thread;
  do not mutate Plan configuration, task closures, or shared inputs during runs.
  History uses operation-local SQLite connections; writes can serialize.
- Bulk Rust topology compilation, selection, order copying, and run initialization
  detach from Python using owned Rust data. Tiny state transitions remain attached;
  one Python coordinator owns each run's mutable native scheduler.

## History and reuse

- Storage is opt-in at an explicit local path. No import-time directory creation,
  background daemon, network request, or task execution.
- Run history stores graph identity/version, run IDs, node states, timestamps,
  and bounded diagnostics. Raw argument/result persistence is off by default;
  default diagnostics contain exception types only; an optional bounded formatter can redact additional details.
- Queries distinguish latest attempt, latest success, and compatible reusable
  result. Wall-clock timestamps alone are insufficient ordering or identity.
- The store must reject incompatible schema versions clearly. A disconnected
  reader must not mark another live process's run abandoned; run ownership and
  liveness/recovery use OS file leases and are crash-tested.
- A crash between an external effect and its success record leaves an unknown
  outcome. History cannot establish exactly-once effects.
- Caching requires an explicit key/version contract and an available persisted
  result. No automatic hashing of arbitrary Python objects or unsafe pickle loading.
- Resume creates a new run linked to its source. It preserves prior evidence and
  records why each node was reused, rerun, or requires a caller decision.

## Success and stopping point

At layer 3, execute a real branching tool workflow and compare integration effort,
correctness, and scheduling overhead with a small direct Python baseline. Record
node counts, task sizes, runtime, platform, and concurrency. Set a workload-based
performance budget before optimizing; make no unmeasured speed claims.
If the component cannot demonstrate simpler dependency management or recovery
value, reassess before adding storage and wider distribution.
