# Layer 0 — repository and native foundation

Status: in progress. Date: 2026-09-15.

## Decisions

- Private `kwip-info/traversal`; independent nested repository; MIT like PyScoped.
- Maturin mixed Python/Rust package. Separate Python-independent `traversal-core`
  crate and internal PyO3 binding crate. No executor or async runtime dependency yet.
- Version 0.1.0a1 / Rust 0.1.0-alpha.1 is a development identity, not a publication.
- Conventional CPython 3.11–3.14 CI target. No abi3/free-threaded compatibility claim yet.
- Canonical skill ships inside the Python package and as a CI artifact. Only
  version/native installation inspection is supported in this layer.

## Required verification

1. Format/lint Rust and Python; compile and test the Rust-only core independently.
2. Build a release wheel, install it, and execute distribution/skill tests.
3. Build the sdist, rebuild its wheel, and test in an isolated environment.
4. Confirm the wheel and sdist contain the skill and exclude runtime/build state.
5. Validate skill frontmatter and run remote CI after private repository creation.

## Evidence

Local macOS arm64 verification uses Rust 1.98.1, PyO3 0.29.2, and Maturin 1.15.0.

- `cargo fmt --all --check`, `cargo clippy --locked -p traversal-core -- -D warnings`: pass.
- `cargo test --locked -p traversal-core`: passes compilation; zero behavioral
  tests because graph behavior is not implemented in this layer.
- `uv run --no-sync ruff check .` and `ruff format --check .`: pass.
- Release wheel built and installed on CPython 3.14.5: two distribution tests pass,
  including compiled-extension loading, version agreement, and shipped skill execution.
- Source archive rebuilt and installed in a separate CPython 3.11.14 environment:
  two distribution tests pass. Archive inspection exposed missing docs/test globs;
  corrected inclusion to explicit file patterns, including license and dependency lock.
- Wheel/archive inspection: skill included, no caches, run databases, or credentials.
- Bundled skill-creator `quick_validate.py`: valid.
- GitHub creation verified: `kwip-info/traversal`, `isPrivate: true`.

Remote CI pending initial push. No behavioral execution or performance claim.
