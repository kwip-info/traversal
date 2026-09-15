# Performance evidence for 0.2.0

Measured on macOS 26.6.2 arm64, 10 logical CPUs, CPython 3.14.5 regular and
free-threaded builds. Three measured repetitions after a warm-up, medians below.
Both runs used the detached-Rust 0.2.0 candidate before its version bump (metadata
in the raw records therefore says 0.1.0). GIL status was true/false respectively.
History was disabled. These are one-machine observations, not performance promises.

## Eight-worker DAG results

| Workload | Regular Python | Free-threaded Python | Free-threaded speedup vs its sequential baseline |
| --- | ---: | ---: | ---: |
| python_cpu | 274.5 ms | 80.2 ms | 3.09× |
| native_cpu | 28.1 ms | 32.3 ms | 3.83× |
| blocking_io | 51.2 ms | 50.4 ms | 7.69× |
| tiny_nodes | 17.9 ms | 15.4 ms | 0.00× |
| native_topology | 21.8 ms | 14.5 ms | 3.48× |

The Python CPU workload used 16 independent modular-arithmetic loops of 500,000
iterations followed by a sum. Eight free-threaded workers consumed about 6.9 CPU
seconds per wall second, versus about 1.0 on regular Python: actual parallel CPU
execution. The measured graph was 3.42× faster across runtimes, and 3.09× faster
than its free-threaded direct sequential baseline. This is qualification of the
existing thread executor on 3.14t, not a claim that a PyO3 flag alone caused it.
The unmodified 0.1.0 source already imported without enabling the GIL.

Native CPU used OpenSSL PBKDF2 (100,000 iterations per task), which already releases
the GIL. Blocking I/O used 16 sleeps of 20 ms; real services have different limits.
Tiny work used 512 identity nodes and a join: direct execution takes microseconds,
so scheduling is a loss. Batch tiny operations instead of making each a node.
Native topology compiled eight independent 20,000-node chains and copied their
order/selection through PyO3. Python argument conversion remains attached; bulk
Rust work detaches. This measures the complete boundary, not pure Rust throughput.

Each result file includes all 1/2/4/8-worker samples and direct ThreadPoolExecutor
baselines. Compilation of the outer workload DAG is outside the execution timer;
pool creation and shutdown are inside both threaded baselines. Correctness is
checked for every sample. This synthetic workload does not predict end-to-end
agent latency, memory use, service rate limits, or SQLite contention.

## Reproduce

Install the same Traversal version in regular and free-threaded environments, then
run each interpreter sequentially (not at the same time):

```sh
python benchmarks/multicore.py --repeats 3 --output /tmp/traversal-benchmark.json
```

Compare raw wall/CPU samples and interpreter metadata. Keep workload arguments
identical. See [regular samples](benchmarks/0.2.0-gil.json) and
[free-threaded samples](benchmarks/0.2.0-free-threaded.json). No timing thresholds
are asserted by correctness CI.
