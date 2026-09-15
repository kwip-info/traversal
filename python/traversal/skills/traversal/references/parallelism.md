# Choosing and checking parallel execution

Traversal 0.2.0 supports conventional CPython 3.11–3.14 and free-threaded 3.14t.
The graph API is identical. Choose the runtime for the work:

| Work | Useful execution choice |
| --- | --- |
| HTTP, files, subprocess waits | Synchronous tasks in threads, or genuinely awaitable async tasks; regular Python is sufficient |
| Substantial independent Python CPU work | Synchronous tasks on free-threaded 3.14t |
| Native computation that releases the GIL | Threads can already use multiple cores on regular Python; measure the library's behavior |
| Hundreds of trivial transformations | Batch items inside a node; graph overhead can dominate |

## Optional isolated setup

With uv available:

```sh
uv python install 3.14t
uv venv --python 3.14t .venv-t
uv pip install --python .venv-t 'traversal==0.2.0'
uv run --python .venv-t --no-project python /path/to/this/skill/scripts/check_install.py
uv run --python .venv-t --no-project python /path/to/this/skill/scripts/parallel_example.py
```

Use the actual exported skill path. A free-threaded Python installation from another
provider works too: run its interpreter's `-m pip install traversal==0.2.0`.
A 3.14t-compatible wheel installs without Rust on supported platforms. Free-threaded
3.13, PyPy and other platforms are not release-qualified.

Verify the process **after importing all task dependencies**:

```python
import sys
import sysconfig
import traversal

print(bool(sysconfig.get_config_var("Py_GIL_DISABLED")))  # build capability
print(sys._is_gil_enabled())  # False means currently disabled (Python 3.13+)
```

An extension can enable the GIL, and startup flags can enable it too. Investigate
that dependency; do not force the GIL off around an incompatible extension.
Installing Traversal does not replace the interpreter. Free-threading benefits
independent synchronous functions in the thread pool; an `async def` CPU loop
still blocks the graph's event loop.

## Ownership and useful granularity

A compiled Plan can run concurrently; each run owns its scheduler, outputs and
failures. Context variables are copied into synchronous task calls. Graph building
is single-owner. Keep Plan configuration unchanged while executing. Objects in
arguments, task closures and outputs remain references: give each branch its own
mutable data or protect shared updates with a lock. Do not assume a compound
read/modify/write operation is atomic because a container protects its internals.

`max_concurrency` applies per run. Several concurrent runs each have their own
pool; native libraries may have pools too. Start with a small worker count and
measure oversubscription, task duration and peak memory on the actual workload.
Only ready branches can overlap: a chain remains sequential. The coordinator and
Python argument conversion still have costs. Opt-in History writes can serialize
in SQLite. Rust bulk topology operations detach, but that alone cannot accelerate
Python task bodies on a regular interpreter.

Use `parallel_example.py` to verify results and runtime mode, not to claim a speedup.
For measurements use repository `benchmarks/multicore.py`: compare identical work
at 1/2/4/8 workers, direct sequential and thread-pool baselines, and both runtimes.
Report hardware, GIL state and task sizes. Retain the graph when dependencies and
structured outcomes justify it; batch tiny work inside nodes.

Cancellation keeps the same contract on both runtimes: stop new admission, cancel
cooperative async work, drain running synchronous calls. It cannot undo effects.
