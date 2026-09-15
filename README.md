# Traversal

Concurrent DAG execution for Python, powered by Rust.

**Development status: layer 0, native package foundation only.** No `Graph` API,
execution engine, persistence, or caching is implemented yet. No PyPI release has
been published; the name is not reserved. Owner: Trevor Ewert / KWIP LLC. MIT licensed.

Traversal is being built as a small in-process library: Rust manages graph
structure and execution state; ordinary Python functions perform the work.
The graph schedules eligible nodes concurrently. External tools schedule runs.

## Build and verify

Requires Rust (1.83 minimum declared; see phase evidence for tested versions),
CPython 3.11+, and uv. CI targets conventional CPython 3.11–3.14 on Linux, macOS,
and Windows; only completed CI results establish tested combinations. PyPy and
free-threaded Python are outside the initial support target.

```sh
uv sync --locked --no-install-project
uv run --no-sync maturin build --locked --release --out dist
uv pip install --reinstall --no-deps --python .venv/bin/python dist/*.whl
uv run --no-sync pytest
cargo test --locked -p traversal-core
```

On Windows use `.venv/Scripts/python.exe` and pass the built wheel's actual path.
The wheel loads a real PyO3 extension linked to the separate Rust core. There are
no Python runtime dependencies. Build tools and test tools are development dependencies.

## Downloadable skill

The canonical skill is [python/traversal/skills/traversal](python/traversal/skills/traversal/SKILL.md).
It is included in wheels and source distributions, and CI uploads a standalone
`traversal-skill` archive. Copy its `traversal` folder to your agent's skill directory.
For Codex this is normally `~/.codex/skills/traversal`. The repository is private;
GitHub downloads currently require repository access.

The skill tracks implemented behavior, with an executable installation check.
It does not advertise future API examples as working features.

## Development

- [Execution contract](docs/CONTRACT.md)
- [Layer plan and gates](docs/development/PLAN.md)
- [Layer 0 evidence](docs/development/PHASE_0.md)
- [Next layer: graph core](docs/development/PHASE_1.md)

Package publication is separate from development CI. No publishing workflow is enabled.
