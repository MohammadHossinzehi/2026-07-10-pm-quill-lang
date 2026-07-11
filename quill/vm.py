"""The stack-based virtual machine that executes compiled Quill
bytecode. This is the "runtime": no tree walking happens here, only a
flat instruction dispatch loop over a Python list acting as the value
stack, plus a stack of CallFrames for function calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from .chunk import OpCode
from .objects import NativeFunction, QuillFunction

MAX_FRAMES = 256


class QuillRuntimeError(Exception):
    def __init__(self, message: str, line: Optional[int] = None):
        if line is not None:
            message = f"[line {line}] {message}"
        super().__init__(message)


@dataclass
class CallFrame:
    function: QuillFunction
    ip: int
    slot_base: int


def _is_truthy(value: Any) -> bool:
    if value is None or value is False:
        return False
    return True


def stringify(value: Any) -> str:
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _clock(_args: List[Any]) -> float:
    import time
    return time.time()


class VM:
    def __init__(self, print_fn: Optional[Callable[[str], None]] = None):
        self.stack: List[Any] = []
        self.frames: List[CallFrame] = []
        self.globals: dict = {}
        self.print_fn = print_fn or (lambda s: print(s))
        self._define_native("clock", 0, _clock)

    def _define_native(self, name: str, arity: int, fn) -> None:
        self.globals[name] = NativeFunction(name, arity, fn)

    # -- public entry point ----------------------------------------------------

    def interpret(self, function: QuillFunction) -> Any:
        self.stack = [function]
        self.frames = [CallFrame(function, 0, 0)]
        return self._run()

    # -- stack helpers -----------------------------------------------------------

    def _push(self, value: Any) -> None:
        self.stack.append(value)

    def _pop(self) -> Any:
        return self.stack.pop()

    def _peek(self, distance: int = 0) -> Any:
        return self.stack[-1 - distance]

    # -- main loop -----------------------------------------------------------

    def _run(self) -> Any:
        frame = self.frames[-1]

        def read_byte() -> int:
            nonlocal frame
            b = frame.function.chunk.code[frame.ip]
            frame.ip += 1
            return b

        def read_constant() -> Any:
            return frame.function.chunk.constants[read_byte()]

        while True:
            instruction = read_byte()

            if instruction == OpCode.CONSTANT:
                self._push(read_constant())

            elif instruction == OpCode.NIL:
                self._push(None)

            elif instruction == OpCode.TRUE:
                self._push(True)

            elif instruction == OpCode.FALSE:
                self._push(False)

            elif instruction == OpCode.POP:
                self._pop()

            elif instruction == OpCode.GET_LOCAL:
                slot = read_byte()
                self._push(self.stack[frame.slot_base + slot])

            elif instruction == OpCode.SET_LOCAL:
                slot = read_byte()
                self.stack[frame.slot_base + slot] = self._peek(0)

            elif instruction == OpCode.GET_GLOBAL:
                name = read_constant()
                if name not in self.globals:
                    raise QuillRuntimeError(f"Undefined variable '{name}'.")
                self._push(self.globals[name])

            elif instruction == OpCode.DEFINE_GLOBAL:
                name = read_constant()
                self.globals[name] = self._pop()

            elif instruction == OpCode.SET_GLOBAL:
                name = read_constant()
                if name not in self.globals:
                    raise QuillRuntimeError(f"Undefined variable '{name}'.")
                self.globals[name] = self._peek(0)

            elif instruction == OpCode.EQUAL:
                b = self._pop()
                a = self._pop()
                self._push(self._values_equal(a, b))

            elif instruction == OpCode.GREATER:
                b, a = self._pop_numbers()
                self._push(a > b)

            elif instruction == OpCode.LESS:
                b, a = self._pop_numbers()
                self._push(a < b)

            elif instruction == OpCode.ADD:
                b = self._pop()
                a = self._pop()
                if isinstance(a, str) and isinstance(b, str):
                    self._push(a + b)
                elif isinstance(a, (int, float)) and not isinstance(a, bool) and \
                        isinstance(b, (int, float)) and not isinstance(b, bool):
                    self._push(a + b)
                else:
                    raise QuillRuntimeError("Operands must be two numbers or two strings.")

            elif instruction == OpCode.SUBTRACT:
                b, a = self._pop_numbers()
                self._push(a - b)

            elif instruction == OpCode.MULTIPLY:
                b, a = self._pop_numbers()
                self._push(a * b)

            elif instruction == OpCode.DIVIDE:
                b, a = self._pop_numbers()
                if b == 0:
                    raise QuillRuntimeError("Division by zero.")
                result = a / b
                self._push(result)

            elif instruction == OpCode.NOT:
                self._push(not _is_truthy(self._pop()))

            elif instruction == OpCode.NEGATE:
                value = self._pop()
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise QuillRuntimeError("Operand must be a number.")
                self._push(-value)

            elif instruction == OpCode.PRINT:
                self.print_fn(stringify(self._pop()))

            elif instruction == OpCode.JUMP:
                offset = read_byte()
                frame.ip += offset

            elif instruction == OpCode.JUMP_IF_FALSE:
                offset = read_byte()
                if not _is_truthy(self._peek(0)):
                    frame.ip += offset

            elif instruction == OpCode.LOOP:
                offset = read_byte()
                frame.ip -= offset

            elif instruction == OpCode.CALL:
                arg_count = read_byte()
                self._call_value(arg_count)
                frame = self.frames[-1]

            elif instruction == OpCode.RETURN:
                result = self._pop()
                finished_frame = self.frames.pop()
                del self.stack[finished_frame.slot_base:]
                if not self.frames:
                    return result
                self._push(result)
                frame = self.frames[-1]

            else:  # pragma: no cover - unreachable
                raise QuillRuntimeError(f"Unknown opcode {instruction}")

    # -- helpers ---------------------------------------------------------------

    def _pop_numbers(self):
        b = self._pop()
        a = self._pop()
        if isinstance(a, bool) or isinstance(b, bool) or \
                not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            raise QuillRuntimeError("Operands must be numbers.")
        return b, a

    def _values_equal(self, a: Any, b: Any) -> bool:
        if type(a) in (int, float) and type(b) in (int, float):
            return a == b
        if type(a) != type(b):
            return False
        return a == b

    def _call_value(self, arg_count: int) -> None:
        callee = self._peek(arg_count)

        if isinstance(callee, QuillFunction):
            if arg_count != callee.arity:
                raise QuillRuntimeError(
                    f"Expected {callee.arity} arguments but got {arg_count}.")
            if len(self.frames) >= MAX_FRAMES:
                raise QuillRuntimeError("Stack overflow.")
            slot_base = len(self.stack) - arg_count - 1
            self.frames.append(CallFrame(callee, 0, slot_base))

        elif isinstance(callee, NativeFunction):
            if callee.arity != -1 and arg_count != callee.arity:
                raise QuillRuntimeError(
                    f"Expected {callee.arity} arguments but got {arg_count}.")
            args = self.stack[len(self.stack) - arg_count:]
            del self.stack[len(self.stack) - arg_count - 1:]
            result = callee.fn(args)
            self._push(result)

        else:
            raise QuillRuntimeError("Can only call functions.")
