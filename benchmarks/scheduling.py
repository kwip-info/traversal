"""Compare a 100-node, 1 ms blocking workload with direct Python threading.

Gate budget chosen before measurement: graph <= direct * 2 + 20 ms, median of 7.
This is a small adoption workload, not a claim of universal performance.
"""

import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from traversal import Graph


def work():
    time.sleep(0.001)
    return 1


def direct():
    with ThreadPoolExecutor(max_workers=4) as pool:
        return sum(pool.map(lambda _: work(), range(100)))


graph = Graph("benchmark")
nodes = [graph.add(str(i), work) for i in range(100)]
end = graph.add("sum", sum, nodes)
plan = graph.compile(end)


def measured(fn):
    times = []
    for _ in range(7):
        start = time.perf_counter()
        assert fn() == 100
        times.append(time.perf_counter() - start)
    return statistics.median(times)


if __name__ == "__main__":
    baseline = measured(direct)
    execution = measured(lambda: plan.run().outputs["sum"])
    budget = baseline * 2 + 0.020
    print(
        json.dumps(
            {
                "nodes": 101,
                "concurrency": 4,
                "task_sleep_seconds": 0.001,
                "direct_seconds": baseline,
                "graph_seconds": execution,
                "budget_seconds": budget,
                "passed": execution <= budget,
            },
            indent=2,
        )
    )
    if execution > budget:
        raise SystemExit("Adoption benchmark exceeded its budget")
