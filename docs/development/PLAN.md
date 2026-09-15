# Traversal development plan

Owner: Trevor Ewert. Implementer: Codex. Started: 2026-09-15.
Scope: free/MIT public library. On 2026-09-15 Trevor explicitly authorized completing all layers, PyPI prerelease/final publication, and a kwip.info library page. Earlier experiment-only boundaries are superseded.

| Layer | Scope | Gate | Status |
| --- | --- | --- | --- |
| 0 | Contract, Rust/PyO3 package, CI, downloadable skill | Installed native wheel and skill example pass; source rebuild works | Complete |
| 1 | Rust graph structure, validation, target closure | Cycles, missing/foreign references, fan-out, joins, disconnected graphs | Complete |
| 2 | Rust readiness and execution state | Completion permutations, capacity, exactly-once admission per attempt, failure propagation | Planned |
| 3 | Python execution adapters and public API | Controlled real concurrency, joins, exceptions, cancellation, one real tool workflow | Planned |
| 4 | Local SQLite history | History query semantics, concurrent access, crash recovery and ownership | Planned |
| 5 | Explicit result reuse and resume | Key invalidation, missing/corrupt artifacts, unknown side effects | Planned |
| 6 | Adoption and release readiness | Benchmarks, wheel matrix, fresh skill-led usage, documented limits | Planned |

Before each layer, expand its phase file with decisions and behavioral tests.
Do not implement later layers in the same change merely because scaffolding exists.
A gate records actual commands/results and unresolved limits; code presence is not evidence.
Update the canonical packaged skill in the same change as supported behavior.
CI executes skill examples from the installed wheel. Public APIs do not appear in
supported examples before implementation. Core tests must not require Python.

Next checkpoint: graph-core implementation under PHASE_1.md.
Investment checkpoint: after layer 3, demonstrate value on one real KWIP workflow
as evidence for the already authorized persistence and launch work.
