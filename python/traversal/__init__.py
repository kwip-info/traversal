"""Traversal: native package foundation. Graph execution is not available yet."""

from ._native import __version__ as _rust_version

__version__ = _rust_version.replace("-alpha.", "a")
__all__ = ["__version__"]
