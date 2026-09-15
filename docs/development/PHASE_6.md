# Layer 6 — release and adoption

Status: active. Layers 1–5 complete.

Harden cancellation (including repeated cancellation), failure bookkeeping and
cache invalidation when a forced recomputation cannot be persisted. Execute the
versioned skill's setup/branch/history/reuse examples from installed release wheels.
Test source archive rebuild, 12-platform/Python CI matrix, native Rust tests and
lint. Publish 0.1.0 only after exact-commit CI succeeds; OIDC publishes tag-gated
artifacts, and a fresh PyPI install verifies the public distribution.

Keep API documentation and public claims aligned with implemented constraints:
local filesystem history, cooperative async cancellation, blocking task timeouts,
explicit cache compatibility, no process/distributed executor, no exactly-once effects.
Record reproducible benchmark results and wheel sizes instead of generic speed claims.
Build kwip.info page from current production origin/main in an isolated worktree;
validate accessibility, responsive layout, links, imagery and skill download before
publishing. Preserve current production Atlas/Contacts changes.

## Local candidate evidence

35 Python tests pass on macOS arm64 CPython 3.14.5 and on a separate CPython 3.11.14
source-distribution install. Rust 11 tests, fmt and clippy pass. All skill examples
(installation, branching, history/reuse) execute from installed package resources.
The skill exporter is tested for completeness and refusing overwrite.

Prerelease 0.1.0a2 published successfully via OIDC run 34979258679 with 12 wheels
and one source archive. A fresh PyPI wheel-only install on CPython 3.11.14 exported
its skill and completed the quickstart. No API token was created or exposed.
