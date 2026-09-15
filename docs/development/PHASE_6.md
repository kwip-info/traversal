# Layer 6 — release and adoption

Status: complete. Traversal 0.1.0 is publicly released.

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

## Public release evidence — 2026-09-15

- Release code: `e0e12492f961878cd100c3091dee97efbc165c55`, tag `v0.1.0`.
- Exact-commit CI: https://github.com/kwip-info/traversal/actions/runs/34981060005
  All 14 jobs passed (Rust, source rebuild, 12 installed-wheel combinations).
- OIDC publication: https://github.com/kwip-info/traversal/actions/runs/34981327872
- PyPI: https://pypi.org/project/traversal/0.1.0/ — 12 wheels and one source archive.
- Fresh CPython 3.11 wheel-only installation from PyPI passed exported
  `check_install.py`, `quickstart.py`, and `history_example.py`.
- GitHub release: https://github.com/kwip-info/traversal/releases/tag/v0.1.0
- Live page: https://kwip.info/technology/traversal/
  Site commit `44a22bd`, based on current production `51db219`.
- Website validation: 15-page links/metadata checker; no horizontal overflow at
  320, 375, 768, 1440 px; zero axe WCAG A/AA violations at 320, 768, 1440 px;
  keyboard skip link and copy control checked; graph/social artwork inspected.
- Public skill ZIP SHA-256:
  `3b56323577332e8776312e0a7c204ca44a6a15be3d5e420b7b8a18cd1d94e845`.
  Website and GitHub release match; contents match the packaged canonical skill.

Supported wheels: conventional CPython 3.11–3.14, macOS arm64, Windows x86_64,
Linux x86_64 (manylinux 2.28). Other supported build targets require Rust/source
installation. Execution and storage limits remain documented in API.md.
