"""Verify independent CPU branches; use a benchmark for performance claims."""

import sys
import sysconfig

from traversal import Graph


def calculate(seed):
    value = seed
    for n in range(50_000):
        value = (value * 33 + n) % 1_000_000_007
    return value


def main():
    graph = Graph("parallel-check")
    branches = [graph.add(f"chunk-{i}", calculate, i) for i in range(4)]
    total = graph.add("total", sum, branches)
    report = graph.compile(total).run(max_concurrency=4).raise_for_status()
    assert report.outputs["total"] == sum(calculate(i) for i in range(4))
    print(f"free_threaded_build={bool(sysconfig.get_config_var('Py_GIL_DISABLED'))}")
    print(f"gil_enabled={getattr(sys, '_is_gil_enabled', lambda: True)()}")
    print(f"parallel branches verified; total={report.outputs['total']}")


if __name__ == "__main__":
    main()
