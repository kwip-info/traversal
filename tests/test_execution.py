import asyncio
import contextvars
import threading

import pytest
from traversal import Graph, RunError


def test_branch_overlap_and_early_release():
    async def scenario():
        a_started, b_started, c_done = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def a():
            a_started.set()
            await b_started.wait()
            return 2

        async def b():
            b_started.set()
            await a_started.wait()
            await c_done.wait()  # b cannot finish before a's child has executed
            return 3

        async def c(value):
            c_done.set()
            return value * 10

        g = Graph("branches")
        na, nb = g.add("a", a), g.add("b", b)
        nc = g.add("c", c, na)
        end = g.add("join", lambda x, y: x + y, nc, nb)
        report = await asyncio.wait_for(g.compile(end).arun(max_concurrency=2), 5)
        assert report.outputs["join"] == 23
        assert report.succeeded

    asyncio.run(scenario())


def test_blocking_threads_overlap_and_context():
    barrier = threading.Barrier(2, timeout=5)
    value = contextvars.ContextVar("value", default="missing")
    value.set("present")

    def work():
        barrier.wait()
        return value.get()

    g = Graph("threads")
    a, b = g.add("a", work), g.add("b", work)
    assert list(g.compile(a, b).run(max_concurrency=2).outputs.values()) == ["present", "present"]


def test_capacity_and_shared_ancestor():
    async def scenario():
        active, maximum, calls = 0, 0, 0

        async def work():
            nonlocal active, maximum, calls
            active += 1
            calls += 1
            maximum = max(maximum, active)
            await asyncio.sleep(0)  # scheduling yield, not a timing assertion
            active -= 1
            return 1

        g = Graph("capacity")
        root = g.add("root", lambda: 1)
        nodes = [g.add(str(i), work, after=[root]) for i in range(20)]
        report = await g.compile(*nodes).arun(max_concurrency=3)
        assert report.succeeded and calls == 20 and maximum == 3

    asyncio.run(scenario())


def test_failure_and_independent_branch():
    def bad():
        raise ValueError("deliberate")

    g = Graph("fail")
    a = g.add("bad", bad)
    blocked = g.add("child", lambda _: pytest.fail("must not run"), a)
    good = g.add("good", lambda: 42)
    report = g.compile(blocked, good).run()
    assert report.states == {"bad": "failed", "child": "blocked", "good": "succeeded"}
    assert report.failures["bad"].message == "deliberate"
    assert "raise ValueError" in report.failures["bad"].traceback
    with pytest.raises(RunError) as caught:
        report.raise_for_status()
    assert caught.value.report is report


def test_bindings_freeze_and_target_selection():
    g = Graph("bindings")
    a = g.add("a", lambda: 5)
    values = [a]
    end = g.add("end", lambda value: value, {"list": values, "tuple": (a,)})
    plan = g.compile(end)
    values.append(9)
    g.add("unused", lambda: pytest.fail("not selected"))
    report = plan.run()
    assert report.outputs["end"] == {"list": [5], "tuple": (5,)}
    assert "unused" not in report.states
    assert plan.describe()["order"] == ["a", "end"]


def test_foreign_nodes_cycles_invalid_targets():
    g, other = Graph("one"), Graph("two")
    a = g.add("a", lambda: 1)
    foreign = other.add("a", lambda: 2)
    with pytest.raises(ValueError):
        g.add("x", lambda _: None, foreign)
    b = g.add("b", lambda x: x, a)
    g.depends_on(a, b)
    with pytest.raises(ValueError, match="cycle"):
        g.compile(b)
    with pytest.raises(ValueError):
        other.compile(a)
    with pytest.raises(ValueError):
        other.compile()
    with pytest.raises(ValueError):
        other.compile("missing")


def test_cancellation_drains_blocking_work():
    async def scenario():
        loop = asyncio.get_running_loop()
        started = asyncio.Event()
        release, finished = threading.Event(), threading.Event()

        def work():
            loop.call_soon_threadsafe(started.set)
            if not release.wait(5):
                raise RuntimeError("test did not release thread")
            finished.set()

        g = Graph("cancel")
        a = g.add("a", work)
        b = g.add("b", lambda: pytest.fail("cancelled child ran"), after=[a])
        running = asyncio.create_task(g.compile(b).arun())
        await asyncio.wait_for(started.wait(), 5)
        running.cancel()
        await asyncio.sleep(0)
        assert not running.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await running
        assert finished.is_set()

    asyncio.run(scenario())


def test_async_cancellation_and_loop_guard():
    async def scenario():
        started, stopped = asyncio.Event(), asyncio.Event()

        async def work():
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

        g = Graph("async-cancel")
        a = g.add("a", work)
        plan = g.compile(a)
        with pytest.raises(RuntimeError, match="arun"):
            plan.run()
        task = asyncio.create_task(plan.arun())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stopped.is_set()

    asyncio.run(scenario())


@pytest.mark.parametrize("capacity", [0, -1, True, 1.5])
def test_invalid_capacity(capacity):
    g = Graph("invalid")
    a = g.add("a", lambda: 0)
    with pytest.raises(ValueError):
        g.compile(a).run(max_concurrency=capacity)


@pytest.mark.parametrize("exception", [SystemExit, KeyboardInterrupt])
def test_task_base_exceptions_are_reported(exception):
    g = Graph("base-exception")

    def task():
        raise exception("task exit")

    result = g.run(g.add("task", task))
    assert result.failures["task"].exception_type == exception.__name__


def test_repeated_cancel_keeps_lease_until_thread_finishes(tmp_path):
    from traversal import History, RunActiveError

    async def scenario():
        h = History(tmp_path / "cancel.sqlite")
        started, release = asyncio.Event(), threading.Event()
        loop = asyncio.get_running_loop()

        def task():
            loop.call_soon_threadsafe(started.set)
            assert release.wait(5)

        g = Graph("repeat-cancel", store=h)
        running = asyncio.create_task(g.compile(g.add("task", task)).arun())
        await started.wait()
        running.cancel()
        await asyncio.sleep(0)
        running.cancel()
        await asyncio.sleep(0)
        run_id = h.latest(graph="repeat-cancel")["id"]
        with pytest.raises(RunActiveError):
            h.recover(run_id)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await running
        assert h.get(run_id)["status"] == "interrupted"

    asyncio.run(scenario())


def test_sync_callable_returning_awaitable_fails_clearly():
    async def actual():
        return 1

    g = Graph("bad-adapter")
    result = g.run(g.add("wrapped", lambda: actual()))
    assert result.failures["wrapped"].exception_type == "TypeError"
