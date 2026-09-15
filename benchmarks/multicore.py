"""Fixed-workload scaling evidence; no timing assertions or runtime dependencies.

Run on regular and free-threaded CPython with identical arguments. Compilation is
outside DAG execution timings. Native CPU uses OpenSSL PBKDF2; topology measures
the actual PyO3 boundary separately. No history is enabled in these measurements.
"""

import argparse
import hashlib
import json
import os
import platform
import ssl
import statistics
import sys
import sysconfig
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from traversal import Graph, __version__, _native


def measure(fn, repeats, expected):
    assert fn() == expected  # warm-up and correctness outside samples
    samples = []
    for _ in range(repeats):
        wall, cpu = time.perf_counter(), time.process_time()
        result = fn()
        cpu, wall = time.process_time() - cpu, time.perf_counter() - wall
        assert result == expected
        samples.append({"wall_seconds": wall, "process_cpu_seconds": cpu})
    return {
        "median_seconds": statistics.median(s["wall_seconds"] for s in samples),
        "median_cpu_per_wall": statistics.median(
            s["process_cpu_seconds"] / s["wall_seconds"] for s in samples
        ),
        "samples": samples,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--repeats", type=int, default=5)
    p.add_argument("--python-iterations", type=int, default=500_000)
    p.add_argument("--native-iterations", type=int, default=100_000)
    args = p.parse_args()
    if min(args.repeats, args.python_iterations, args.native_iterations) < 1:
        p.error("repeat and iteration counts must be positive")

    def python_cpu(i):
        value = i
        for n in range(args.python_iterations):
            value = (value * 33 + n) % 1_000_000_007
        return value

    def native_cpu(i):
        result = hashlib.pbkdf2_hmac(
            "sha256", str(i).encode(), b"traversal-benchmark", args.native_iterations
        )
        return int.from_bytes(result[:4], "big")

    def blocking_io(i):
        time.sleep(0.02)
        return i

    names = [str(i) for i in range(20_000)]
    dependencies = [[]] + [[i - 1] for i in range(1, len(names))]

    def topology(i):
        value = _native.Topology(names, dependencies)
        assert value.order()[-1] == len(names) - 1
        return sum(value.select([names[-1]])) + i

    results = []
    workloads = [
        ("python_cpu", python_cpu, 16),
        ("native_cpu", native_cpu, 16),
        ("blocking_io", blocking_io, 16),
        ("tiny_nodes", lambda i: i, 512),
        ("native_topology", topology, 8),
    ]
    for name, function, count in workloads:
        expected = sum(function(i) for i in range(count))
        sequential = measure(
            lambda function=function, count=count: sum(function(i) for i in range(count)),
            args.repeats,
            expected,
        )
        graph = Graph(name)
        nodes = [graph.add(str(i), function, i) for i in range(count)]
        end = graph.add("join", sum, nodes)
        plan = graph.compile(end)
        for workers in (1, 2, 4, 8):

            def direct(workers=workers, function=function, count=count):
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    return sum(pool.map(function, range(count)))

            baseline = measure(direct, args.repeats, expected)
            dag = measure(
                lambda plan=plan, workers=workers: plan.run(max_concurrency=workers).outputs[
                    "join"
                ],
                args.repeats,
                expected,
            )
            row = {
                "workload": name,
                "tasks": count,
                "workers": workers,
                "sequential": sequential,
                "thread_pool": baseline,
                "traversal": dag,
                "speedup_vs_sequential": sequential["median_seconds"] / dag["median_seconds"],
            }
            results.append(row)
            print(
                f"{name:16} workers={workers} DAG={dag['median_seconds']:.4f}s "
                f"speedup={row['speedup_vs_sequential']:.2f}x",
                flush=True,
            )
    data = {
        "traversal": __version__,
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "logical_cpus": os.cpu_count(),
        "free_threaded_build": bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
        "gil_enabled": getattr(sys, "_is_gil_enabled", lambda: True)(),
        "openssl": ssl.OPENSSL_VERSION,
        "parameters": {k: v for k, v in vars(args).items() if k != "output"},
        "io_sleep_seconds": 0.02,
        "topology_nodes": len(names),
        "history": False,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    main()
