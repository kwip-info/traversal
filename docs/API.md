# Traversal 0.1.0 API

## Setup

`python -m pip install traversal==0.1.0` in a project virtual environment.
Supported release wheels: conventional CPython 3.11–3.14, Linux x86_64 glibc 2.28+,
macOS arm64, Windows x86_64. No Python runtime dependencies; wheel users need no Rust.

## Graph construction

- `Graph(name, version="1", store=None)`: name/version identify your workflow.
  `store` accepts a History instance or explicit filesystem path. Without it,
  execution creates no history or cache files.
- `add(name, function, *args, after=(), cache=None, **kwargs) -> Node`: records an
  ordinary callable. Node arguments express data dependencies. Lists, tuples and
  dictionary values are traversed; other objects are opaque. Node keys in dicts
  are rejected. `after` supplies ordering-only dependencies. `cache` accepts Cache.
  Both keywords are reserved; wrap tasks that need them as function parameters.
- `depends_on(node, *dependencies)`: adds ordering constraints before compilation.
- `compile(*targets) -> Plan`: validates the entire graph and freezes topology and
  binding containers. Targets are Node handles or names. At least one is required.
- `run(*targets, max_concurrency=4)`: shorthand for compile(...).run(...).

Plans retain function/object references. They don't freeze closures or deep-copy
arbitrary objects. Don't concurrently mutate shared task values without coordination.

## Execution and inspection

- `plan.describe()`: JSON-compatible topology, selection, ordering dependencies,
  callable/module identifiers and repeat-safety declarations. Does not run code.
- `plan.run(max_concurrency=4, previous=None, rerun=()) -> RunReport`.
- `await plan.arun(...)`: same options on an existing asyncio event loop.
- `plan.explain_run(previous=None, rerun=())`: run/reuse/unselected/decision reasons
  without task invocation. It reads stored artifacts when reuse is possible.
- `plan.resume(run_id, rerun=(), max_concurrency=4)`: linked new run; requires a store.

Rust admits eligible nodes up to the capacity. Async callables run on the event
loop; sync callables run in threads with copied contextvars. A sync callable
returning an awaitable must be wrapped in an async function. Python CPU work
still obeys the GIL. Cancellation requests cancel async tasks, stop new admission,
and drain running threads before propagation. A task that never returns can delay
cancellation indefinitely: configure task-specific I/O timeouts.

Task exceptions (including task-local SystemExit/KeyboardInterrupt) are reported
without exiting the whole graph. Failure blocks descendants; independent branches
continue. No automatic retries. Scheduler bookkeeping/storage failures raise to the
caller and leave interrupted/unknown evidence where the outcome is uncertain.

## Reports

`RunReport` exposes graph, optional run_id, read-only mappings of states, outputs,
failures, and reuse reasons. `succeeded` is true if all selected nodes succeeded or
were reused. `raise_for_status()` returns the report or raises RunError(report).
Failure contains exception_type, message and traceback. In-memory reports contain
full task data; share them only deliberately. Successful intermediate outputs are
retained for inspection until the report is released.

States: unselected, pending, ready, running, succeeded, reused, failed, blocked,
cancelled. Recovered in-flight persisted work may be unknown. There is no
exactly-once promise for external effects, no rollback, and no forced thread stop.

## Local history

`History(path, error_formatter=None, max_cache_bytes=1048576)` uses SQLite WAL,
FULL synchronous commits, and adjacent per-run OS lock files. It is designed for
local filesystems on one machine, not network shares or multiple hosts.

- `runs(graph=None, status=None, limit=20)` returns newest records by monotonic
  database sequence (1–1000 per query).
- `latest(graph=..., status=None)` returns a record or None. Use
  `status="succeeded"` to distinguish last success from last attempt.
- `get(run_id)` returns run metadata and node records; missing IDs raise KeyError.
- `recover(run_id)` explicitly checks the run lease. RunActiveError means its owner
  remains. Abandoned running nodes become unknown, unstarted work cancelled, and
  the run interrupted. Ordinary queries don't make those changes.

Default persistence stores task names/states/timestamps and exception types, not
arguments, outputs, or exception messages. The optional error_formatter receives
Failure and returns redacted text, capped at 4096 characters. Its own error falls
back to the exception type. Cache is an explicit exception to output non-persistence.
No background cleanup runs. Caller owns retention and local file permissions.

## Explicit cache and resume

`Cache(key)` declares repeat/skip safety and a caller-maintained compatibility key.
Change it when code, literal inputs, configuration or external revisions change.
Traversal does not hash arbitrary Python values, function source, or environments.
Fingerprints incorporate graph name/version, node name/key and all dependencies.
An ancestor lacking Cache prevents downstream reuse.

Only finite JSON-native outputs with string dict keys persist (1 MiB default).
No pickle or arbitrary object deserialization. Cache misses, unsupported outputs,
oversize results and integrity failures are visible in report.reuse/explain_run.
Task success does not guarantee persistence. Integrity checks detect corruption;
they do not authenticate a maliciously edited local store.

Resume preserves prior history and links a new run. Previously started tasks
without Cache require explicit `rerun=["node-name"]`; otherwise
ResumeDecisionError.decisions lists unresolved nodes. Before consenting, inspect
external state and authorization. A prior unfinished run must be explicitly
recovered first. Changing Cache keys permits repeat-safe nodes to recompute.
Forced rerun names apply exactly to those nodes; other cache compatibility rules
remain in effect. A normal run without `previous` executes non-cache tasks anew.

## Agent skill and CLI

`python -m traversal skill --output NEW_DIRECTORY` exports the exact matching skill;
it refuses to overwrite an existing directory. Skill scripts check installation,
branch execution, history and reuse using sample data.

`python -m traversal history PATH --graph NAME --limit 20` lists runs.
`python -m traversal history PATH --run RUN_ID` inspects a run. No task code executes;
opening an older supported database can perform its documented schema migration.
