"""Audit independent Git repositories concurrently, then join their summaries.

Usage: python examples/tool_workflow.py /path/to/repo /path/to/another/repo
Only reads Git state. Task bodies use standard Python subprocess tooling.
"""

import json
import subprocess
import sys
from pathlib import Path

from traversal import Graph


def inspect_repository(path):
    def git(*args):
        return subprocess.run(
            ["git", "-C", str(path), *args], check=True, capture_output=True, text=True
        ).stdout.strip()

    return {
        "repository": path.name,
        "commit": git("rev-parse", "--short", "HEAD"),
        "changed_files": len(git("status", "--porcelain").splitlines()),
    }


def main(paths):
    graph = Graph("repository-audit")
    sources = [
        graph.add(f"repository-{i}", inspect_repository, Path(path).resolve())
        for i, path in enumerate(paths)
    ]
    summary = graph.add(
        "summary",
        lambda rows: {
            "repositories": rows,
            "total_changed_files": sum(r["changed_files"] for r in rows),
        },
        sources,
    )
    report = graph.run(summary).raise_for_status()
    print(json.dumps(report.outputs["summary"], indent=2))


if __name__ == "__main__":
    if not sys.argv[1:]:
        raise SystemExit("Pass at least one Git repository path")
    main(sys.argv[1:])
