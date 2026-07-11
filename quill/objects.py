"""Runtime object types that can flow through the VM stack in addition
to the primitive Python types (float/int, str, bool, None) which are
used directly as Quill numbers, strings, booleans, and nil.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List

from .chunk import Chunk


@dataclass
class QuillFunction:
    name: str
    arity: int
    chunk: Chunk = field(default_factory=Chunk)

    def __repr__(self) -> str:
        if self.name == "<script>":
            return "<script>"
        return f"<fn {self.name}>"


@dataclass
class NativeFunction:
    name: str
    arity: int
    fn: Callable[[List[object]], object]

    def __repr__(self) -> str:
        return f"<native fn {self.name}>"
