# Traversal development plan

Owner: Trevor Ewert. Implementer: Codex. Started: 2026-09-15.
Scope: free/MIT public library. On 2026-09-15 Trevor explicitly authorized completing all layers, PyPI prerelease/final publication, and a kwip.info library page. Earlier experiment-only boundaries are superseded.

| Layer | Scope | Gate | Status |
| --- | --- | --- | --- |
| 0 | Contract, Rust/PyO3 package, CI, downloadable skill | Installed native wheel and skill example pass; source rebuild works | Complete |
| 1 | Rust graph structure, validation, target closure | Cycles, missing/foreign references, fan-out, joins, disconnected graphs | Complete |
| 2 | Rust readiness and execution state | Completion permutations, capacity, exactly-once admission per attempt, failure propagation | Complete |
| 3 | Python execution adapters and public API | Controlled real concurrency, joins, exceptions, cancellation, one real tool workflow | Complete |
| 4 | Local SQLite history | History query semantics, concurrent access, crash recovery and ownership | Complete |
| 5 | Explicit result reuse and resume | Key invalidation, missing/corrupt artifacts, unknown side effects | Complete |
| 6 | Adoption and release readiness | Benchmarks, wheel matrix, fresh skill-led usage, documented limits | Complete |

Before each layer, expand its phase file with decisions and behavioral tests.
Do not implement later layers in the same change merely because scaffolding exists.
A gate records actual commands/results and unresolved limits; code presence is not evidence.
Update the canonical packaged skill in the same change as supported behavior.
CI executes skill examples from the installed wheel. Public APIs do not appear in
supported examples before implementation. Core tests must not require Python.

Active release: [0.2.0 multicore qualification](RELEASE_0_2.md), authorized by Trevor on 2026-09-15. Preserve the completed six-layer scope; qualify free-threaded execution, native detachment, and distribution together.
