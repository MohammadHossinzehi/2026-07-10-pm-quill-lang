"""Bytecode representation: opcodes, and the Chunk container that holds
a function's compiled instruction stream plus its constant pool.
"""

from __future__ import annotations

from enum import IntEnum, auto
from typing import Any, List


class OpCode(IntEnum):
    CONSTANT = 0
    NIL = auto()
    TRUE = auto()
    FALSE = auto()
    POP = auto()
    GET_LOCAL = auto()
    SET_LOCAL = auto()
    GET_GLOBAL = auto()
    DEFINE_GLOBAL = auto()
    SET_GLOBAL = auto()
    EQUAL = auto()
    GREATER = auto()
    LESS = auto()
    ADD = auto()
    SUBTRACT = auto()
    MULTIPLY = auto()
    DIVIDE = auto()
    NOT = auto()
    NEGATE = auto()
    PRINT = auto()
    JUMP = auto()
    JUMP_IF_FALSE = auto()
    LOOP = auto()
    CALL = auto()
    RETURN = auto()


class Chunk:
    """One chunk per function (the top-level script counts as a function
    too). `code` is a flat list of ints: opcodes and their operand bytes
    interleaved, matching the classic clox design so jump patching and
    operand widths are explicit rather than hidden behind objects.
    """

    def __init__(self) -> None:
        self.code: List[int] = []
        self.lines: List[int] = []
        self.constants: List[Any] = []

    def write(self, byte: int, line: int) -> int:
        self.code.append(byte)
        self.lines.append(line)
        return len(self.code) - 1

    def add_constant(self, value: Any) -> int:
        self.constants.append(value)
        return len(self.constants) - 1

    def __len__(self) -> int:
        return len(self.code)
