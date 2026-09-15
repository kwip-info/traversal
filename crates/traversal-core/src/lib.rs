//! Python-independent home of Traversal's graph and execution state.
//!
//! Layer 0 establishes the build boundary. Graph behavior begins in layer 1.

/// Version of the linked Rust core, exposed for installation diagnostics.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
