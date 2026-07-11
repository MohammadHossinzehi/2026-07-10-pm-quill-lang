"""High-level convenience wrapper tying lexer -> parser -> compiler ->
VM together, with a single entry point (`run_source`) used by both the
CLI script runner and the REPL, and by the test suite.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from .compiler import CompileError, compile_program
from .lexer import LexError, tokenize
from .parser import ParseError, parse
from .vm import QuillRuntimeError, VM


class QuillError(Exception):
    """Wraps any lex/parse/compile/runtime error with a uniform interface."""


def run_source(source: str, vm: Optional[VM] = None,
                print_fn: Optional[Callable[[str], None]] = None) -> Any:
    """Compile and run a string of Quill source. Returns the value the
    top-level script implicitly "returns" (nil unless the script itself
    ends with a return, which is unusual but allowed).

    Raises QuillError wrapping the underlying LexError/ParseError/
    CompileError/QuillRuntimeError with a readable message.
    """
    if vm is None:
        vm = VM(print_fn=print_fn)

    try:
        tokens = tokenize(source)
        statements = parse(tokens)
        function = compile_program(statements)
    except (LexError, ParseError, CompileError) as exc:
        raise QuillError(str(exc)) from exc

    try:
        return vm.interpret(function)
    except QuillRuntimeError as exc:
        raise QuillError(str(exc)) from exc


def run_file(path: str) -> None:
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    run_source(source)
