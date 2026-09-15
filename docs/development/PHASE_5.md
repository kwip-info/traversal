# Layer 5 — explicit reusable results and resume

Status: complete. Layer 4 complete.

Cache(key) explicitly declares a node's computation safe to repeat or skip and
identifies its code/inputs/configuration version. Only JSON-native finite results
are cached, bounded to 1 MiB by default, with SHA-256 integrity checks. No pickle.
Fingerprints include graph identity/version, node name/key and all dependency
fingerprints. An uncached ancestor prevents downstream reuse; no implicit hashing
of arbitrary values, closures, source code or external state.

Plan.explain_run(previous=None, rerun=()) returns run/reuse/decision reasons without
calling tasks. Plan.resume(run_id, rerun=()) creates a linked new run. Previously
started non-cache nodes require explicit named rerun consent if not reusable;
unknown effects are never silently retried. Cache nodes are explicitly repeat-safe.
Running previous runs require explicit recovery first. Reads don't recover.

SQLite schema 2 adds bounded JSON results and per-node cache fingerprint/reason;
schema 1 upgrades transactionally. Missing/corrupt/non-JSON results are cache misses,
reported with reasons. Task success does not imply result persistence succeeded.

Gate: cache reuse and key/version/upstream invalidation, uncached dependency,
changed topology, missing/corrupt result, unsupported result type, explicit resume
decisions, source linkage, and migration. Verify both run explanation and execution.

## Evidence

28 Python tests and 11 Rust tests pass locally. Tests cover cache hit paths,
upstream key and graph version invalidation, uncached ancestors, corrupted/missing
JSON, tuple output remaining successful without persistence, explicit effect reruns,
unknown-effect refusal, prior-run linkage and schema-1 migration. A self-cancelling
node regression now prevents a cancelled graph from being recorded as successful.
