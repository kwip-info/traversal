"""Export the version-matched agent skill from an installed package."""

import argparse
from importlib.resources import files
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(prog="python -m traversal")
    sub = parser.add_subparsers(dest="command", required=True)
    skill = sub.add_parser("skill", help="Export this package's agent skill")
    skill.add_argument("--output", type=Path, required=True, help="New directory to create")
    args = parser.parse_args()
    destination = args.output.expanduser()
    destination.mkdir(parents=True, exist_ok=False)
    source = files("traversal").joinpath("skills/traversal")

    def copy(tree, target):
        for item in tree.iterdir():
            if item.name == "__pycache__" or item.name.endswith(".pyc"):
                continue
            path = target / item.name
            if item.is_dir():
                path.mkdir()
                copy(item, path)
            else:
                path.write_bytes(item.read_bytes())

    copy(source, destination)
    print(f"Exported Traversal skill to {destination}")


if __name__ == "__main__":
    main()
