use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::sync::Arc;
use traversal_core::{Builder, GraphError, RunState, State, Topology};

// Only owned Rust values enter this helper. Python conversion and exception
// creation remain on the attached side of the boundary.
fn compile_topology(
    names: Vec<String>,
    dependencies: Vec<Vec<usize>>,
) -> Result<Topology, GraphError> {
    if names.len() != dependencies.len() {
        return Err(GraphError("dependency length mismatch".into()));
    }
    let mut b = Builder::new();
    let ids: Vec<_> = names.iter().map(|n| b.add(n)).collect::<Result<_, _>>()?;
    for (i, deps) in dependencies.iter().enumerate() {
        for &dep in deps {
            let d = ids
                .get(dep)
                .ok_or_else(|| GraphError("unknown dependency index".into()))?;
            b.depends_on(ids[i], *d)?;
        }
    }
    b.compile()
}

#[pyclass(name = "Topology", frozen)]
struct PyTopology {
    graph: Arc<Topology>,
}
#[pymethods]
impl PyTopology {
    #[new]
    fn new(py: Python<'_>, names: Vec<String>, dependencies: Vec<Vec<usize>>) -> PyResult<Self> {
        Ok(Self {
            graph: Arc::new(
                py.detach(|| compile_topology(names, dependencies))
                    .map_err(|e| PyValueError::new_err(e.to_string()))?,
            ),
        })
    }
    fn order(&self, py: Python<'_>) -> Vec<usize> {
        py.detach(|| self.graph.order().to_vec())
    }
    fn select(&self, py: Python<'_>, targets: Vec<String>) -> PyResult<Vec<bool>> {
        py.detach(|| self.graph.select(&targets))
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }
    fn start(&self, py: Python<'_>, targets: Vec<String>, capacity: usize) -> PyResult<PyRun> {
        Ok(PyRun {
            run: py
                .detach(|| RunState::new(self.graph.clone(), &targets, capacity))
                .map_err(|e| PyValueError::new_err(e.to_string()))?,
        })
    }
}
#[pyclass(name = "RunState")]
struct PyRun {
    run: RunState,
}
#[pymethods]
impl PyRun {
    fn admit(&mut self) -> Vec<usize> {
        self.run.admit()
    }
    fn finish(&mut self, node: usize, outcome: &str) -> PyResult<()> {
        let state = match outcome {
            "succeeded" => State::Succeeded,
            "reused" => State::Reused,
            "failed" => State::Failed,
            "cancelled" => State::Cancelled,
            _ => return Err(PyValueError::new_err("invalid outcome")),
        };
        self.run
            .finish(node, state)
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }
    fn cancel(&mut self) {
        self.run.cancel()
    }
    fn done(&self) -> bool {
        self.run.done()
    }
    fn states(&self) -> Vec<&'static str> {
        self.run.states().iter().map(|s| s.as_str()).collect()
    }
}
// The public coordinator owns each mutable RunState; PyO3 exclusive borrowing
// rejects overlapping mutable calls to the internal class. No GIL-based locks.
#[pymodule(gil_used = false)]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("__version__", traversal_core::VERSION)?;
    module.add_class::<PyTopology>()?;
    module.add_class::<PyRun>()?;
    Ok(())
}
