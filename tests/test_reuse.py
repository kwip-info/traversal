import asyncio
import sqlite3

import pytest
from traversal import Cache, Graph, History, ResumeDecisionError


def make_plan(history, calls, key="1", version="1"):
    g = Graph("cached", store=history, version=version)

    def source():
        calls.append("source")
        return 5

    def double(n):
        calls.append("double")
        return n * 2

    a = g.add("source", source, cache=Cache(key))
    b = g.add("double", double, a, cache=Cache("double-v1"))
    return g.compile(b)


def test_reuse_and_upstream_invalidation(tmp_path):
    h, calls = History(tmp_path / "runs.sqlite"), []
    p = make_plan(h, calls)
    first = p.run()
    assert calls == ["source", "double"]
    assert [n["action"] for n in p.explain_run()["nodes"]] == ["reuse", "reuse"]
    second = p.run()
    assert second.outputs["double"] == 10 and set(second.states.values()) == {"reused"}
    assert second.succeeded and len(calls) == 2
    resumed = p.resume(first.run_id)
    assert h.get(resumed.run_id)["source_run_id"] == first.run_id
    changed = make_plan(h, calls, key="2")
    assert all(n["action"] == "run" for n in changed.explain_run()["nodes"])
    changed.run()
    assert len(calls) == 4
    assert all(
        n["action"] == "run" for n in make_plan(h, calls, version="2").explain_run()["nodes"]
    )


def test_uncached_ancestor_prevents_reuse(tmp_path):
    h = History(tmp_path / "runs.sqlite")
    g = Graph("uncached", store=h)
    a = g.add("a", lambda: 5)
    b = g.add("b", lambda n: n, a, cache=Cache("b-v1"))
    p = g.compile(b)
    p.run()
    assert all(n["action"] == "run" for n in p.explain_run()["nodes"])


def test_missing_corrupt_and_non_json_results(tmp_path):
    h, calls = History(tmp_path / "runs.sqlite"), []
    p = make_plan(h, calls)
    p.run()
    with sqlite3.connect(h.path) as db:
        db.execute("UPDATE results SET payload='corrupt'")
    assert all(n["action"] == "run" for n in p.explain_run()["nodes"])
    p.run()
    with sqlite3.connect(h.path) as db:
        db.execute("DELETE FROM results")
    p.run()
    assert len(calls) == 6
    g = Graph("tuple", store=h)
    t = g.add("tuple", lambda: (1, 2), cache=Cache("tuple"))
    r = g.run(t)
    assert r.succeeded and r.outputs["tuple"] == (1, 2)
    assert "not persisted" in r.reuse["tuple"]


def test_resume_requires_named_decision_for_effects(tmp_path):
    h = History(tmp_path / "runs.sqlite")
    calls = []
    g = Graph("effects", store=h)
    a = g.add("send", lambda: calls.append("sent"))
    p = g.compile(a)
    first = p.run()
    assert p.explain_run(previous=first.run_id)["nodes"][0]["action"] == "decision"
    with pytest.raises(ResumeDecisionError) as exc:
        p.resume(first.run_id)
    assert exc.value.decisions == ["send"] and calls == ["sent"]
    second = p.resume(first.run_id, rerun=["send"])
    assert calls == ["sent", "sent"] and second.succeeded
    assert h.get(second.run_id)["source_run_id"] == first.run_id
    with pytest.raises(ValueError):
        p.resume(first.run_id, rerun=["typo"])


def test_unknown_effect_never_silently_repeats(tmp_path):
    h = History(tmp_path / "runs.sqlite")
    run_id, lease = h._start("effect", "1", ["write"], [True])
    h._running(run_id, "write")
    lease.close()
    h.recover(run_id)
    g = Graph("effect", store=h)
    a = g.add("write", lambda: pytest.fail("must not replay"))
    with pytest.raises(ResumeDecisionError):
        g.compile(a).resume(run_id)


def test_schema_one_migrates_without_losing_history(tmp_path):
    path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE runs (seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE,graph TEXT,graph_version TEXT,status TEXT,started_at REAL,finished_at REAL,source_run_id TEXT)"
        )
        db.execute(
            "CREATE TABLE nodes(run_id TEXT,name TEXT,state TEXT,started_at REAL,finished_at REAL,error TEXT,PRIMARY KEY(run_id,name))"
        )
        db.execute(
            "INSERT INTO runs(id,graph,graph_version,status,started_at) VALUES ('old','g','1','succeeded',1)"
        )
        db.execute("PRAGMA user_version=1")
    h = History(path)
    assert h.latest(graph="g")["id"] == "old"
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2


def test_self_cancel_is_not_recorded_as_success(tmp_path):
    async def cancel():
        raise asyncio.CancelledError()

    h = History(tmp_path / "cancel.sqlite")
    g = Graph("cancel", store=h)
    r = g.run(g.add("cancel", cancel))
    assert not r.succeeded
    assert h.get(r.run_id)["status"] == "failed"


def test_failed_persistence_does_not_leave_stale_cached_result(tmp_path):
    h = History(tmp_path / "cache.sqlite")
    current = [1]
    g = Graph("forced", store=h)
    a = g.add("a", lambda: current[0], cache=Cache("caller-version"))
    p = g.compile(a)
    p.run()
    current[0] = (1, 2)
    r = p.run(rerun=["a"])
    assert "not persisted" in r.reuse["a"]
    assert p.explain_run()["nodes"][0]["action"] == "run"
