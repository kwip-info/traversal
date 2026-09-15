# Traversal

**Concurrent DAG execution for Python, powered by Rust.** Free, MIT licensed,
in-process, and built for ordinary Python functions and tool calls.

Traversal owns dependencies, readiness, concurrency limits, and structured node
outcomes. Your functions own the work. Use an external scheduler to start runs.
No service, account, telemetry, or Python runtime dependency is required.

## Install

```sh
python -m pip install 'traversal==0.1.0'
```

This first release includes graph execution, local run history, explicit JSON
result reuse and guarded resume. Conventional CPython 3.11–3.14 is CI-tested.
Release wheels target Linux x86_64 (glibc 2.28+), macOS Apple Silicon, and Windows
x86_64. Source builds require Rust and Maturin.

## A graph in a few lines

```python
from traversal import Graph

graph = Graph("report")
source = graph.add("source", lambda: 5)
left = graph.add("left", lambda n: n * 2, source)
right = graph.add("right", lambda n: n + 3, source)
total = graph.add("total", sum, [left, right])

plan = graph.compile(total)
print(plan.describe())
report = plan.run(max_concurrency=2).raise_for_status()
print(report.outputs["total"])  # 18
```

Left and right are independently eligible after source completes. Total waits
for both. Only requested targets and their ancestors run. Nested lists, tuples,
and dictionary values can contain Node references. `after=[node]` adds an ordering
dependency without passing a result. `after` is a reserved API keyword.

Async functions run on the event loop; ordinary functions use a bounded thread
pool. Inside an event loop, use `await plan.arun()`. Rust scheduling does not
bypass the GIL for CPU-bound Python. Cancellation stops new admission and drains
blocking work; tasks should set their own I/O timeouts.

Inspect `report.states`, `report.outputs`, and `report.failures`. Failures include
exception type, message and traceback. Independent branches continue; descendants
of a failed node are blocked. Calling `raise_for_status()` is optional.

Plans freeze topology and binding containers. Arbitrary Python objects remain
references; shared mutation requires caller coordination. Reports retain all
successful intermediate outputs until released. Rerunning performs work again:
there is no exactly-once guarantee for external actions.

## Remember runs and reuse results

```python
from traversal import Cache, Graph, History

history = History(".traversal/runs.sqlite")
graph = Graph("totals", version="1", store=history)
source = graph.add("source", lambda: [1, 2, 3], cache=Cache("input-v1"))
total = graph.add("total", sum, source, cache=Cache("sum-v1"))
plan = graph.compile(total)
first = plan.run().raise_for_status()
print(history.latest(graph="totals"))
print(plan.explain_run(previous=first.run_id))
second = plan.resume(first.run_id)  # Reuses compatible JSON results.
```

Cache is an explicit declaration that a computation is safe to repeat or skip.
Its key must cover changing code, inputs and configuration. All ancestors need
keys for downstream reuse. Previously started non-cache work requires a named
rerun decision during resume; unknown external effects are never silently replayed.
History is opt-in and local. Default records omit task payloads and error messages;
caching explicitly opts into bounded JSON result storage. No pickle.

See the [complete API and boundaries](docs/API.md).

## Install the agent skill

The version-matched skill ships in the wheel:

```sh
python -m traversal skill --output ~/.codex/skills/traversal
```

Use your agent's skill directory, or export to any new directory. The command
refuses to overwrite an existing folder. The [canonical skill](python/traversal/skills/traversal/SKILL.md)
teaches PyPI setup, graph construction, execution, and failure inspection. Its
examples are executed in CI against the installed wheel. A standalone download
is also available in the CI run's `traversal-skill` artifact.

## Develop

Install Rust and uv, then:

```sh
uv sync --locked --no-install-project
uv run --no-sync maturin develop --release
uv run --no-sync pytest
cargo test --locked -p traversal-core
```

Rust topology/state and PyO3 bindings are separate crates. Python adapters have no
third-party runtime dependency. PyPy, free-threaded CPython, process pools,
distributed workers, connectors and calendar scheduling are outside this release.

- [Contract](docs/CONTRACT.md)
- [Layer plan and evidence](docs/development/PLAN.md)
- [Real Git-tool workflow](examples/tool_workflow.py)
- [Scheduling benchmark](benchmarks/scheduling.py)

Owner: Trevor Ewert / KWIP LLC. [MIT license](LICENSE).
