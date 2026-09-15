"""A runnable fan-out/fan-in example for the installed Traversal version."""

from traversal import Graph


def main():
    graph = Graph("quickstart")
    source = graph.add("source", lambda: 5)
    left = graph.add("left", lambda n: n * 2, source)
    right = graph.add("right", lambda n: n + 3, source)
    total = graph.add("total", sum, [left, right])
    report = graph.run(total, max_concurrency=2).raise_for_status()
    assert report.outputs["total"] == 18
    print("Traversal quickstart: total = 18")


if __name__ == "__main__":
    main()
