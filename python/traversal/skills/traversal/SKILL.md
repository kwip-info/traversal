---
name: traversal
description: Use the Traversal Python library for dependency graphs and execution inspection when a task explicitly selects Traversal. Check the installed version first; the current pre-alpha contains only the native package foundation.
---

# Traversal

## Compatibility and current capability

This skill ships with Traversal **0.1.0a1, layer 0**. Only `traversal.__version__`
is public. Graph construction, execution, concurrency, history, caching, and
resume are planned and unavailable. Do not generate calls to those APIs yet.

Run [scripts/check_install.py](scripts/check_install.py) with the Python interpreter
that will use Traversal. It imports the compiled Rust extension, checks installed
package metadata, and verifies compatibility with this skill. If it fails, use
the matching source/wheel and skill; do not install an unrelated package or
silently replace the user's selected library.

## Working on the library

When the task is Traversal development, read the repository's `AGENTS.md`,
`docs/CONTRACT.md`, and active phase under `docs/development/` before editing.
They describe planned guarantees, not currently implemented APIs.

For the intended architecture and boundaries, read
[references/semantics.md](references/semantics.md). Update this skill, that
reference, and executable examples whenever supported behavior changes.

Graph execution does not grant permission for external actions. Future replay
or retry features must respect the caller's existing authorization and explicit
node replay rules.
