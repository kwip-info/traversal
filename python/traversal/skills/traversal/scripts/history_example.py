"""Verify local history and reusable results using disposable sample data."""

from pathlib import Path
from tempfile import TemporaryDirectory

from traversal import Cache, Graph, History


def main():
    with TemporaryDirectory() as directory:
        history = History(Path(directory) / "runs.sqlite")
        graph = Graph("history-example", store=history)
        source = graph.add("source", lambda: [1, 2, 3], cache=Cache("sample-input-v1"))
        total = graph.add("total", sum, source, cache=Cache("sum-v1"))
        plan = graph.compile(total)
        first = plan.run().raise_for_status()
        assert history.latest(graph="history-example")["id"] == first.run_id
        assert all(n["action"] == "reuse" for n in plan.explain_run()["nodes"])
        second = plan.resume(first.run_id).raise_for_status()
        assert second.outputs["total"] == 6
        assert set(second.states.values()) == {"reused"}
        assert history.get(second.run_id)["source_run_id"] == first.run_id
        print("Traversal history: durable lookup and explicit reuse verified")


if __name__ == "__main__":
    main()
