# Traversal development guidance

Read docs/development/PLAN.md, docs/CONTRACT.md, and the active phase before changing behavior.
Owner: Trevor Ewert / KWIP LLC. This repository owns Traversal implementation and its distributable skill.

- Work one layer at a time. Expand its design and test cases before implementation; record commands, outcomes, limitations, and decisions before advancing.
- Rust owns graph structure and execution eligibility. Python adapters invoke ordinary callables; external schedulers invoke runs.
- Test branching, joins, completion permutations, failures, and cancellation with controlled synchronization. Timing benchmarks are separate from correctness tests.
- A recorded success is not a reusable result. Never promise exactly-once external effects or infer replay safety.
- Keep the canonical skill in python/traversal/skills/traversal current in the same change as public behavior. Run its examples against the installed wheel.
- Keep planned APIs out of supported examples. Do not add placeholder Graph/run/cache methods.
- Keep dependencies justified. No hosted services, telemetry, connector catalog, calendar scheduler, or distributed workers in this library.
- Never commit run databases, arbitrary task data, credentials, build caches, or release archives.
- GitHub setup and development pushes are authorized. Package publication and public release are separate actions.
