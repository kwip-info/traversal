---
name: traversal
description: Set up and use Traversal to execute dependent Python functions concurrently, inspect plans, and diagnose node failures. Use for Traversal workflows or when a branching tool workflow benefits from explicit dependency execution.
---

# Traversal

## Install first

This skill matches **Traversal 0.1.0** (first release). Check the task's Python
interpreter and existing environment before installing. In a project virtualenv:

```sh
python -m pip install 'traversal==0.1.0'
python -c "import traversal; print(traversal.__version__)"
```

Python 3.11–3.14 is the initial tested range. Wheels target Linux x86_64
(glibc 2.28+), macOS Apple Silicon, and Windows x86_64. A supported wheel requires
no local Rust installation. If pip attempts a source build, first verify the
interpreter/platform; source builds require Rust and Maturin. Do not claim that
installing Rust makes an untested platform supported.

Run [scripts/check_install.py](scripts/check_install.py) with that interpreter to
check native loading and version compatibility. Run [scripts/quickstart.py](scripts/quickstart.py)
to verify a branching graph. If the package version differs, export its matching
skill into a new directory using `python -m traversal skill --output ./traversal-skill`.
The exporter refuses to overwrite an existing directory.

## Build and run

Use ordinary functions as tasks. `Graph.add(name, function, *args, after=(), **kwargs)`
records work without executing it. Pass returned Node references inside arguments
(including built-in lists, tuples and dictionary values) to express data dependencies.
Use `after=[node]` for ordering without passing a result. Names must be unique.
`after` is reserved by the graph API; wrap a callable that needs an `after` argument.

Compile explicit targets with `graph.compile(target)`; inspect `plan.describe()`.
Run with `plan.run(max_concurrency=4)` or `await plan.arun(...)` inside an event loop.
Async callables run on the event loop; blocking callables use threads. The GIL still
limits CPU-bound Python threads. Do not promise process/distributed execution.

Inspect `report.states`, `report.outputs`, and `report.failures`. Failures include
exception type, message, and traceback; `report.raise_for_status()` raises RunError
with the report attached. Independent branches continue; failed descendants are
blocked. Reports may contain sensitive task data; do not publish them automatically.

Run [scripts/history_example.py](scripts/history_example.py) to verify local
history and reuse with disposable sample data. The CLI can list existing records:
`python -m traversal history .traversal/runs.sqlite --graph NAME --limit 20`.

## Boundaries and recovery

For durable run lookup, construct `History(".traversal/runs.sqlite")` and pass it
as `Graph("name", store=history)`. Inspect `history.latest(graph="name")`,
`history.latest(graph="name", status="succeeded")`, and `history.get(report.run_id)`.
The default persists metadata and exception types, not input/output payloads or
exception messages. Read [references/history.md](references/history.md) before recovery.
For result reuse, explicitly declare a repeat-safe node with `cache=Cache("key")`.
Change the key whenever its code, inputs, configuration, or external revision
changes. All ancestors also need cache keys for downstream reuse. Only bounded
JSON-native results persist; inspect `report.reuse` for misses or skipped storage.

Inspect `plan.explain_run(previous=run_id)` before `plan.resume(run_id)`.
Previously started nodes without Cache require named `rerun=["node"]` decisions;
do not supply that list merely to clear an exception. Inspect the external effect
and existing user authorization first. ResumeDecisionError lists unresolved nodes.
`cache` is another reserved graph keyword. Read the history reference for details. Re-running executes tasks again, including their
external effects; the library grants no authorization for sends or publications.
Cancelling `arun` stops new admission and drains running threads before propagating
cancellation; it cannot undo or forcibly stop a blocking call. Shared mutable values
remain the caller's responsibility.

Read [references/semantics.md](references/semantics.md) for dependency and execution
rules. For library development, follow repository AGENTS.md and its active phase.
Choose plain Python for trivial one-call tasks; use Traversal when branching,
joining, and structured outcomes earn its dependency.
