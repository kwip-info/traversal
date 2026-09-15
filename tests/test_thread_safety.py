"""Synchronized concurrency checks, also run under the free-threaded interpreter."""

import contextvars
import subprocess
import sys
import sysconfig
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from traversal import Cache, Graph, History, _native


def test_free_threaded_import_keeps_gil_disabled():
    if not sysconfig.get_config_var("Py_GIL_DISABLED"):
        pytest.skip("requires free-threaded CPython")
    subprocess.run(
        [sys.executable, "-c", "import traversal, sys; assert not sys._is_gil_enabled()"],
        check=True,
        timeout=20,
    )
    assert not sys._is_gil_enabled()


def test_shared_plan_keeps_context_outputs_and_failures_per_run():
    barrier = threading.Barrier(4, timeout=10)
    identity = contextvars.ContextVar("identity")

    def source():
        barrier.wait()
        return {"caller": identity.get()}

    def validate(value):
        if value["caller"] % 2:
            raise ValueError(str(value["caller"]))
        return value["caller"]

    g = Graph("shared-plan")
    root = g.add("source", source)
    checked = g.add("check", validate, root)
    end = g.add("end", lambda value: value + 10, checked)
    plan = g.compile(end)

    def run(i):
        token = identity.set(i)
        try:
            return plan.run(max_concurrency=2)
        finally:
            identity.reset(token)

    with ThreadPoolExecutor(max_workers=4) as pool:
        reports = list(pool.map(run, range(4)))
    for i, report in enumerate(reports):
        assert report.outputs["source"] == {"caller": i}
        if i % 2:
            assert report.states["end"] == "blocked"
            assert report.failures["check"].message == str(i)
        else:
            assert report.outputs["end"] == i + 10
            assert report.succeeded
    assert len({id(r.outputs["source"]) for r in reports}) == 4


def test_concurrent_history_runs_and_later_reuse(tmp_path):
    store = History(tmp_path / "shared.sqlite")
    barrier = threading.Barrier(4, timeout=10)

    def work():
        barrier.wait()
        return {"answer": 42}

    g = Graph("history-threads", store=store)
    root = g.add("work", work, cache=Cache("answer-v1"))
    end = g.add("end", lambda value: value["answer"], root, cache=Cache("extract-v1"))
    plan = g.compile(end)
    # Force this wave to execute: no late caller may reuse and strand the barrier.
    with ThreadPoolExecutor(max_workers=4) as pool:
        reports = list(pool.map(lambda _: plan.run(rerun=["work", "end"]), range(4)))
    assert len({r.run_id for r in reports}) == 4
    for report in reports:
        assert report.outputs["end"] == 42
        record = store.get(report.run_id)
        assert record["status"] == "succeeded"
        assert {n["state"] for n in record["nodes"]} == {"succeeded"}
    reused = plan.run().raise_for_status()
    assert set(reused.states.values()) == {"reused"}
    assert reused.outputs["end"] == 42


def test_shared_native_topology_has_independent_run_states():
    count = 2048
    topology = _native.Topology(
        [str(i) for i in range(count)], [[]] + [[i - 1] for i in range(1, count)]
    )
    barrier = threading.Barrier(4, timeout=10)

    def run(_):
        barrier.wait()
        assert all(topology.select([str(count - 1)]))
        state = topology.start([str(count - 1)], 4)
        visited = []
        while not state.done():
            ready = state.admit()
            assert len(ready) == 1
            visited.extend(ready)
            state.finish(ready[0], "succeeded")
        return visited

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(v == list(range(count)) for v in pool.map(run, range(4)))


@pytest.mark.parametrize(
    "names,deps,match",
    [
        (["a"], [], "length"),
        (["a"], [[1]], "unknown"),
        (["a", "a"], [[], []], "unique"),
        (["a", "b"], [[1], [0]], "cycle"),
    ],
)
def test_native_compile_errors_remain_python_exceptions(names, deps, match):
    with pytest.raises(ValueError, match=match):
        _native.Topology(names, deps)
