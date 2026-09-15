//! Python-independent graph structure and execution state for Traversal.
mod graph;
pub use graph::{Builder, GraphError, NodeId, Topology};
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
