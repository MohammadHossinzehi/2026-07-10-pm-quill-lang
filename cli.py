#!/usr/bin/env python3
"""Command-line entry point for Quill.

Usage:
    python cli.py script.ql     # run a script file
    python cli.py               # start an interactive REPL
"""

import sys

from quill.interpreter import QuillError, run_source
from quill.vm import VM


def run_repl() -> None:
    print(f"Quill REPL (Python {sys.version.split()[0]}) - Ctrl-D to exit")
    vm = VM()
    while True:
        try:
            line = input("quill> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line.strip():
            continue
        try:
            run_source(line, vm=vm)
        except QuillError as exc:
            print(exc)


def run_file(path: str) -> int:
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    try:
        run_source(source)
    except QuillError as exc:
        print(exc, file=sys.stderr)
        return 65
    return 0


def main() -> int:
    if len(sys.argv) > 2:
        print("Usage: cli.py [script]", file=sys.stderr)
        return 64
    if len(sys.argv) == 2:
        return run_file(sys.argv[1])
    run_repl()
    return 0


if __name__ == "__main__":
    sys.exit(main())
