"""Run with the interpreter where Traversal 0.2.0 is installed."""

import sys
import sysconfig
from importlib.metadata import version

import traversal
from traversal import _native


def main():
    installed = version("traversal")
    if installed != "0.2.0":
        raise RuntimeError(f"This skill supports 0.2.0; installed: {installed}")
    if traversal.__version__ != installed or _native.__version__ != "0.2.0":
        raise RuntimeError("Python metadata and native core version disagree; rebuild/reinstall")
    free_threaded = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
    gil = getattr(sys, "_is_gil_enabled", lambda: True)()
    print(
        f"Python {sys.version.split()[0]}: free_threaded_build={free_threaded}; gil_enabled={gil}"
    )
    if free_threaded and gil:
        print("GIL is enabled: check startup flags and imported extension compatibility.")
    print(f"Traversal {installed}: native core loaded; concurrent DAG execution available")


if __name__ == "__main__":
    main()
