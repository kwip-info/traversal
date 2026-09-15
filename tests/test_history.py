import asyncio
import sqlite3
import subprocess
import sys

import pytest
from traversal import Graph, History, RunActiveError


def test_latest_attempt_and_success_and_no_payloads(tmp_path):
    history = History(tmp_path / "runs.sqlite")
    g = Graph("audit", store=history)
    a = g.add("a", lambda: "secret-result")
    success = g.run(a)
    assert success.run_id

    def fail():
        raise ValueError("secret-error-message")

    bad = Graph("audit", store=history)
    b = bad.add("b", fail)
    failed = bad.run(b)
    assert history.latest(graph="audit")["id"] == failed.run_id
    assert history.latest(graph="audit", status="succeeded")["id"] == success.run_id
    record = history.get(failed.run_id)
    assert record["nodes"][0]["error"] == "ValueError"
    assert "secret" not in repr(history.get(success.run_id)) + repr(record)
    assert len(History(history.path).runs(graph="audit")) == 2
    assert history.recover(success.run_id)["status"] == "succeeded"


def test_redaction_and_schema_rejection(tmp_path):
    h = History(
        tmp_path / "redacted.sqlite", error_formatter=lambda f: "redacted: " + f.exception_type
    )
    g = Graph("errors", store=h)

    def bad():
        raise RuntimeError("private")

    r = g.run(g.add("bad", bad))
    assert h.get(r.run_id)["nodes"][0]["error"] == "redacted: RuntimeError"
    with sqlite3.connect(h.path) as db:
        db.execute("PRAGMA user_version=999")
    with pytest.raises(ValueError, match="schema"):
        History(h.path)
    other = tmp_path / "other.sqlite"
    with sqlite3.connect(other) as db:
        db.execute("CREATE TABLE something (x)")
    with pytest.raises(ValueError, match="unrelated"):
        History(other)


def test_active_run_cannot_be_recovered(tmp_path):
    async def scenario():
        h = History(tmp_path / "active.sqlite")
        started, finish = asyncio.Event(), asyncio.Event()

        async def task():
            started.set()
            await finish.wait()
            return 1

        g = Graph("active", store=h)
        running = asyncio.create_task(g.compile(g.add("task", task)).arun())
        await started.wait()
        observer = History(h.path)
        record = observer.latest(graph="active")
        assert record["status"] == "running"
        with pytest.raises(RunActiveError):
            observer.recover(record["id"])
        assert observer.get(record["id"])["status"] == "running"
        finish.set()
        report = await running
        assert h.get(report.run_id)["status"] == "succeeded"

    asyncio.run(scenario())


def test_process_death_retains_unknown_outcome(tmp_path):
    path = tmp_path / "crash.sqlite"
    code = """
import sys,time
from traversal import Graph

def task():
    print("started",flush=True)
    time.sleep(60)

g = Graph("crash", store=sys.argv[1])
a = g.add("effect", task)
b = g.add("child", lambda: 1, after=[a])
g.run(b)
"""
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        # The child writes the marker only after the running state is durable.
        assert child.stdout.readline().strip() == "started"
        h = History(path)
        run_id = h.latest(graph="crash")["id"]
        with pytest.raises(RunActiveError):
            h.recover(run_id)
        child.kill()
        child.wait(timeout=5)
        assert h.get(run_id)["status"] == "running"  # reads don't infer death
        recovered = h.recover(run_id)
        assert recovered["status"] == "interrupted"
        assert [n["state"] for n in recovered["nodes"]] == ["unknown", "cancelled"]
        assert h.recover(run_id) == recovered
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)


def test_storage_start_failure_prevents_work(tmp_path, monkeypatch):
    h = History(tmp_path / "bad.sqlite")

    def refuse(*args):
        raise OSError("disk unavailable")

    monkeypatch.setattr(h, "_start", refuse)
    g = Graph("refuse", store=h)
    a = g.add("a", lambda: pytest.fail("must not execute without durable start"))
    with pytest.raises(OSError):
        g.run(a)


def test_no_store_has_no_run_id():
    g = Graph("memory")
    assert g.run(g.add("a", lambda: 1)).run_id is None
