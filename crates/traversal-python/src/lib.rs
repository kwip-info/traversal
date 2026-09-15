use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::sync::Arc;
use traversal_core::{Builder, RunState, State, Topology};

#[pyclass(name = "Topology", frozen)]
struct PyTopology {
    graph: Arc<Topology>,
}
#[pymethods]
impl PyTopology {
    #[new]
    fn new(names: Vec<String>, dependencies: Vec<Vec<usize>>) -> PyResult<Self> {
        if names.len() != dependencies.len() {
            return Err(PyValueError::new_err("dependency length mismatch"));
        }
        let mut b = Builder::new();
        let ids: Vec<_> = names
            .iter()
            .map(|n| b.add(n))
            .collect::<Result<_, _>>()
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        for (i, deps) in dependencies.iter().enumerate() {
            for &dep in deps {
                let d = ids
                    .get(dep)
                    .ok_or_else(|| PyValueError::new_err("unknown dependency index"))?;
                b.depends_on(ids[i], *d)
                    .map_err(|e| PyValueError::new_err(e.to_string()))?;
            }
        }
        Ok(Self {
            graph: Arc::new(
                b.compile()
                    .map_err(|e| PyValueError::new_err(e.to_string()))?,
            ),
        })
    }
    fn order(&self) -> Vec<usize> {
        self.graph.order().to_vec()
    }
    fn select(&self, targets: Vec<String>) -> PyResult<Vec<bool>> {
        self.graph
            .select(&targets)
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }
    fn start(&self, targets: Vec<String>, capacity: usize) -> PyResult<PyRun> {
        Ok(PyRun {
            run: RunState::new(self.graph.clone(), &targets, capacity)
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
#[pymodule]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("__version__", traversal_core::VERSION)?;
    module.add_class::<PyTopology>()?;
    module.add_class::<PyRun>()?;
    Ok(())
}
