use pyo3::prelude::*;

/// Internal native extension. Public Python exports live in traversal/__init__.py.
#[pymodule]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("__version__", traversal_core::VERSION)?;
    Ok(())
}
