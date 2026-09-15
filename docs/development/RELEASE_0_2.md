# Traversal 0.2.0: multicore qualification

Owner: Trevor Ewert. Authorized 2026-09-15. Status: complete; published and production-verified.

This release deepens the existing graph component. No process executor,
distributed workers, task catalog, or scheduler service is introduced.

## Gates, in order

1. Audit shared state and build the existing code on CPython 3.14t. Confirm that
   importing Traversal does not enable the GIL. Review native mutable borrowing,
   shared Plan bindings, run-local state, SQLite connections, and context copying.
2. Define supported concurrent use and add synchronized regression tests: shared
   compiled plan across threads, independent reports, concurrent history, failure,
   cancellation, and free-threaded import. User callables and shared values remain
   the caller's synchronization responsibility. Graph construction is single-owner.
3. Detach substantial Rust topology work from Python. Keep tiny state transitions
   attached unless measurement justifies a change. Python objects never cross a
   detached closure. Test equivalence and errors.
4. Benchmark fixed workloads at 1/2/4/8 workers on conventional and free-threaded
   interpreters: Python CPU, native CPU, blocking I/O, and tiny-node scheduling.
   Include direct sequential/thread-pool baselines, runtime metadata, repeats and
   raw samples. Timing is evidence, never a correctness assertion.
5. Update API, skill, wheel CI and release tests; version 0.2.0 only after local
   gates pass. Validate installed wheels, source rebuild and exported skill.
   Release only after exact-commit CI. Record measured limits without universal
   speed claims; update the public page and downloadable skill after publication.

## Initial audit

- PyO3 is pinned to 0.29.2, which supports free-threaded CPython and defaults
  modules to not requiring the GIL. Make the declaration explicit for reviewers.
- Native topology is immutable behind Arc. Native RunState mutates through PyO3
  exclusive borrows and is private to each public run's event-loop coordinator.
- Each arun creates its own outputs, failure maps, pending tasks, state and pool.
- A Plan reads shared structural bindings. Concurrent callers must not modify
  Plan/History configuration, callable state or shared input/output objects.
- History uses a fresh SQLite connection per operation; WAL and file leases
  coordinate stores. It does not share a connection across worker threads.
- Sync task contexts are copied separately. Async tasks stay on one event loop;
  a CPU loop inside async def still blocks that loop even without the GIL.
- Existing cancellation drains running threads. No promise of forced termination.

Evidence and outcomes are appended at each gate below.

## Gates 1–4: local evidence

- Baseline source built with `maturin build --locked --release --interpreter` on
  CPython 3.14.5t. Installed wheel left `sys._is_gil_enabled()` false; 35/35
  existing tests passed. No runtime dependency or executor replacement was needed.
- Added eight synchronized/boundary cases: shared Plan/context/report isolation,
  concurrent History writes and later reuse, shared immutable topology with
  independent native runs, native validation errors, and a subprocess import GIL
  assertion. Before Rust edits: 43 passed on 3.14t; 42 passed/1 skipped on 3.14.
  Existing controlled cancellation tests run unchanged in both matrices.
- Detached compile/order/select/start using Rust-owned data and explicit
  `#[pymodule(gil_used = false)]`. Candidate installed 3.14t wheel: 43 passed.
  Tiny per-node mutable transitions stay attached and coordinator-owned.
- `benchmarks/multicore.py --repeats 3` completed independently on both 3.14.5
  interpreters. All checksums agreed. Python CPU at 8 workers: 274.5 ms regular,
  80.2 ms free-threaded; CPU/wall ratios 0.99 and 6.89. Tiny tasks lose to direct
  execution. Full observations, raw samples and limitations are in PERFORMANCE.md.
- Proceeded to version 0.2.0, skill setup/diagnostics, and a 15-wheel matrix
  (3.11–3.14 plus 3.14t across Linux x86_64, macOS arm64, Windows x86_64).
  Source and release validation remain the final gate.

## Gate 5: local packaging checks

- Versioned 0.2.0 installed wheels: regular 3.14.5, 43 passed/1 free-threading
  test skipped; 3.14.5t, 44 passed, including all shipped skill examples.
- Fresh 3.11.14 environment built from the source archive: 43 passed/1 skipped.
- Core Rust: 11 tests passed; rustfmt, core Clippy, Ruff lint/format passed.
- Skill validator passed using an isolated PyYAML tool environment; exported
  installation check and CPU example passed. No PyYAML runtime dependency added.
- CI and release-wheel jobs select their interpreter explicitly; 3.14t jobs must
  pass the import/runtime GIL assertion. Cross-platform results recorded below.

## Public release receipts

- Release commit `55ccef83f0dd8a8e7b3f5d33667007e8a7a1d00a`, tag `v0.2.0`.
- Exact-commit CI: https://github.com/kwip-info/traversal/actions/runs/34998630729
  — all 15 interpreter/platform jobs, core and source build passed.
- Publication: https://github.com/kwip-info/traversal/actions/runs/34998990723
  — 15 actual release wheels tested, source archive checked, OIDC publish succeeded.
- PyPI https://pypi.org/project/traversal/0.2.0/ has 15 wheels and one source archive,
  including cp314t wheels for all three platforms.
- Reinstalled the public PyPI macOS arm64 3.14t wheel using the explicit public
  index: 44 tests passed; GIL stayed disabled. An initial default-index request
  had not yet seen the version; no local wheel fallback was used for this check.
- GitHub release: https://github.com/kwip-info/traversal/releases/tag/v0.2.0
- Production https://kwip.info/technology/traversal/ serves 0.2.0, a flat multicore
  diagram, and syntax-highlighted Python/shell examples. Site merge:
  `447684e78640e6f0f247628891597f651f375a0f`.
- Live skill ZIP SHA-256:
  `3cb9af19f2447e69b4bde370291a06c0178d9b0eb662895dcf14f0ea501935fb`.
  Every ZIP entry matches the packaged canonical skill. Old 0.1.0 download retained.

All release gates complete. Future optimization should follow real workload
profiles; process pools, distributed execution and async CPU offloading remain
outside this release.
