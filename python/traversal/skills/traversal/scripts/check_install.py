"""Run with the interpreter where Traversal 0.1.0a3 is installed."""

from importlib.metadata import version

import traversal
from traversal import _native


def main():
    installed = version("traversal")
    if installed != "0.1.0a3":
        raise RuntimeError(f"This skill supports 0.1.0a3; installed: {installed}")
    if traversal.__version__ != installed or _native.__version__ != "0.1.0-alpha.3":
        raise RuntimeError("Python metadata and native core version disagree; rebuild/reinstall")
    print(f"Traversal {installed}: native core loaded; concurrent DAG execution available")


if __name__ == "__main__":
    main()
