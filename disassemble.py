#!/usr/bin/env python3
"""Standalone bytecode disassembler.

Compiles a Quill script and prints its bytecode in a human-readable
form instead of running it - handy for understanding what the compiler
actually emits, and for debugging the compiler itself.

Usage:
    python disassemble.py examples/fib.ql
"""

import sys

from quill.chunk import Chunk, OpCode
from quill.compiler import compile_program
from quill.lexer import tokenize
from quill.objects import QuillFunction
from quill.parser import parse

# Opcodes that take a single operand byte (an index, slot, or jump offset).
_ONE_OPERAND = {
    OpCode.CONSTANT, OpCode.GET_LOCAL, OpCode.SET_LOCAL, OpCode.GET_GLOBAL,
    OpCode.DEFINE_GLOBAL, OpCode.SET_GLOBAL, OpCode.JUMP, OpCode.JUMP_IF_FALSE,
    OpCode.LOOP, OpCode.CALL,
}


def disassemble_chunk(chunk: Chunk, name: str) -> None:
    print(f"== {name} ==")
    offset = 0
    while offset < len(chunk.code):
        offset = disassemble_instruction(chunk, offset)
    print()


def disassemble_instruction(chunk: Chunk, offset: int) -> int:
    op = OpCode(chunk.code[offset])
    line = chunk.lines[offset] if offset < len(chunk.lines) else -1
    prefix = f"{offset:04d} line {line:>4}  {op.name}"

    if op in _ONE_OPERAND:
        operand = chunk.code[offset + 1]
        if op == OpCode.CONSTANT:
            const = chunk.constants[operand]
            print(f"{prefix:<32} {operand:>4}  ; {const!r}")
        elif op in (OpCode.GET_GLOBAL, OpCode.DEFINE_GLOBAL, OpCode.SET_GLOBAL):
            print(f"{prefix:<32} {operand:>4}  ; {chunk.constants[operand]!r}")
        else:
            print(f"{prefix:<32} {operand:>4}")
        return offset + 2

    print(prefix)
    return offset + 1


def disassemble_function(function: QuillFunction, seen=None) -> None:
    if seen is None:
        seen = set()
    if id(function) in seen:
        return
    seen.add(id(function))
    disassemble_chunk(function.chunk, function.name)
    for constant in function.chunk.constants:
        if isinstance(constant, QuillFunction):
            disassemble_function(constant, seen)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: disassemble.py <script.ql>", file=sys.stderr)
        return 64
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        source = f.read()
    statements = parse(tokenize(source))
    function = compile_program(statements)
    disassemble_function(function)
    return 0


if __name__ == "__main__":
    sys.exit(main())
