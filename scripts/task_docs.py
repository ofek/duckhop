"""Keep the contributor task reference synchronized with mise task metadata."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tomllib


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/reference/dev/tasks.md"


def render() -> str:
    with (ROOT / "mise.toml").open("rb") as source:
        tasks = tomllib.load(source)["tasks"]

    lines = [
        "# Task reference",
        "",
        "<!-- This page is generated from mise.toml by scripts/task_docs.py. -->",
        "",
        "This page is generated from the task descriptions in `mise.toml`. Run `mise run docs:tasks` after changing task metadata; `mise run check:tasks` detects stale output without modifying files.",
        "",
        "Run these commands from the repository root after installing the locked tools and running setup. Publishing helpers are reserved for CI and are omitted from this contributor reference.",
        "",
        "| Command | Behavior |",
        "| --- | --- |",
    ]
    for name, task in sorted(tasks.items()):
        if task.get("hide", False):
            continue
        description = task.get("description")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"Task {name!r} needs a description in mise.toml.")
        description = " ".join(description.split()).replace("|", "\\|")
        lines.append(f"| `mise run {name}` | {description} |")

    lines.extend(
        [
            "",
            "`fmt` and `fix` modify files. The `check` gate is read-only and offline on a prepared checkout. Build-backed C++ analysis and strict documentation validation also run in `verify`; external URL checking stays separate because it needs the network.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check the reference without writing it.")
    arguments = parser.parse_args()
    expected = render()
    if arguments.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != expected:
            print("Task reference is out of date. Run mise run docs:tasks.", file=sys.stderr)
            return 1
        print("Task reference matches mise metadata.")
    else:
        OUTPUT.write_text(expected, encoding="utf-8", newline="\n")
        print(f"Generated {OUTPUT.relative_to(ROOT).as_posix()} from mise metadata.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
