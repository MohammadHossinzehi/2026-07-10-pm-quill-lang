"""Compiler: walks the AST produced by the parser and emits bytecode
into a Chunk, one Chunk per function (the top-level script is treated
as an implicit function called "<script>").

Scope handling follows the classic single-pass-locals approach used by
clox: locals live in a flat array per function and are resolved to
stack slot indices at compile time (OP_GET_LOCAL/OP_SET_LOCAL), while
free (unresolved) names fall back to a global hash-map lookup by name
(OP_GET_GLOBAL/OP_SET_GLOBAL/OP_DEFINE_GLOBAL).

Design scope note: functions can see their own parameters/locals and
globals, but do NOT close over an enclosing function's locals (no
upvalues). Nested `fun` declarations are therefore compiled but should
only rely on globals from an outer scope. This keeps the compiler and
VM small while still supporting recursion, control flow, and
first-class-ish function calls by name. See README "Design decisions".
"""

from __future__ import annotations

from typing import List, Optional

from . import ast_nodes as ast
from .chunk import Chunk, OpCode
from .lexer import TokenType
from .objects import QuillFunction


class CompileError(Exception):
    def __init__(self, message: str, line: int = 0):
        super().__init__(f"[line {line}] Compile error: {message}" if line else f"Compile error: {message}")


class _Local:
    __slots__ = ("name", "depth")

    def __init__(self, name: str, depth: int):
        self.name = name
        self.depth = depth


class _FunctionState:
    def __init__(self, enclosing: Optional["_FunctionState"], name: str, arity: int = 0):
        self.enclosing = enclosing
        self.function = QuillFunction(name=name, arity=arity)
        # Slot 0 of every call frame is reserved for the function value
        # itself (mirrors clox's reserved slot for `this`/the script),
        # so that a real user parameter never collides with slot 0.
        self.locals: List[_Local] = [_Local("", 0)]
        self.scope_depth = 0


_BINARY_OPS = {
    TokenType.PLUS: OpCode.ADD,
    TokenType.MINUS: OpCode.SUBTRACT,
    TokenType.STAR: OpCode.MULTIPLY,
    TokenType.SLASH: OpCode.DIVIDE,
    TokenType.GREATER: OpCode.GREATER,
    TokenType.LESS: OpCode.LESS,
}


class Compiler:
    def __init__(self) -> None:
        self.current: _FunctionState = _FunctionState(None, "<script>", 0)

    # -- public API ----------------------------------------------------------

    def compile(self, statements: List[ast.Stmt]) -> QuillFunction:
        for stmt in statements:
            self._compile_stmt(stmt)
        self._emit_return()
        return self.current.function

    # -- chunk / emit helpers -------------------------------------------------

    @property
    def _chunk(self) -> Chunk:
        return self.current.function.chunk

    def _emit(self, byte: int, line: int = 0) -> int:
        return self._chunk.write(byte, line)

    def _emit_op(self, op: OpCode, line: int = 0) -> int:
        return self._emit(int(op), line)

    def _emit_constant(self, value, line: int = 0) -> None:
        index = self._chunk.add_constant(value)
        self._emit_op(OpCode.CONSTANT, line)
        self._emit(index, line)

    def _emit_return(self) -> None:
        self._emit_op(OpCode.NIL)
        self._emit_op(OpCode.RETURN)

    def _emit_jump(self, op: OpCode) -> int:
        self._emit_op(op)
        self._emit(0xFFFF)  # placeholder operand, patched later
        return len(self._chunk.code) - 1

    def _patch_jump(self, offset: int) -> None:
        jump = len(self._chunk.code) - offset - 1
        self._chunk.code[offset] = jump

    def _emit_loop(self, loop_start: int) -> None:
        self._emit_op(OpCode.LOOP)
        offset = len(self._chunk.code) - loop_start + 1
        self._emit(offset)

    # -- scope helpers ---------------------------------------------------------

    def _begin_scope(self) -> None:
        self.current.scope_depth += 1

    def _end_scope(self) -> None:
        self.current.scope_depth -= 1
        locals_ = self.current.locals
        while locals_ and locals_[-1].depth > self.current.scope_depth:
            self._emit_op(OpCode.POP)
            locals_.pop()

    def _declare_local(self, name: str) -> None:
        for local in reversed(self.current.locals):
            if local.depth != -1 and local.depth < self.current.scope_depth:
                break
            if local.name == name:
                raise CompileError(f"Variable {name!r} already declared in this scope.")
        self.current.locals.append(_Local(name, -1))

    def _mark_initialized(self) -> None:
        if self.current.scope_depth == 0:
            return
        self.current.locals[-1].depth = self.current.scope_depth

    def _resolve_local(self, state: _FunctionState, name: str) -> int:
        for i in range(len(state.locals) - 1, -1, -1):
            if state.locals[i].name == name:
                if state.locals[i].depth == -1:
                    raise CompileError(f"Can't read local variable {name!r} in its own initializer.")
                return i
        return -1

    # -- statements ------------------------------------------------------------

    def _compile_stmt(self, stmt: ast.Stmt) -> None:
        method = getattr(self, f"_stmt_{type(stmt).__name__}")
        method(stmt)

    def _stmt_ExpressionStmt(self, stmt: ast.ExpressionStmt) -> None:
        self._compile_expr(stmt.expression)
        self._emit_op(OpCode.POP)

    def _stmt_PrintStmt(self, stmt: ast.PrintStmt) -> None:
        self._compile_expr(stmt.expression)
        self._emit_op(OpCode.PRINT)

    def _stmt_VarStmt(self, stmt: ast.VarStmt) -> None:
        name = stmt.name.lexeme
        if stmt.initializer is not None:
            self._compile_expr(stmt.initializer)
        else:
            self._emit_op(OpCode.NIL)

        if self.current.scope_depth > 0:
            self._declare_local(name)
            self._mark_initialized()
        else:
            index = self._chunk.add_constant(name)
            self._emit_op(OpCode.DEFINE_GLOBAL)
            self._emit(index)

    def _stmt_BlockStmt(self, stmt: ast.BlockStmt) -> None:
        self._begin_scope()
        for s in stmt.statements:
            self._compile_stmt(s)
        self._end_scope()

    def _stmt_IfStmt(self, stmt: ast.IfStmt) -> None:
        self._compile_expr(stmt.condition)
        then_jump = self._emit_jump(OpCode.JUMP_IF_FALSE)
        self._emit_op(OpCode.POP)
        self._compile_stmt(stmt.then_branch)
        else_jump = self._emit_jump(OpCode.JUMP)
        self._patch_jump(then_jump)
        self._emit_op(OpCode.POP)
        if stmt.else_branch is not None:
            self._compile_stmt(stmt.else_branch)
        self._patch_jump(else_jump)

    def _stmt_WhileStmt(self, stmt: ast.WhileStmt) -> None:
        loop_start = len(self._chunk.code)
        self._compile_expr(stmt.condition)
        exit_jump = self._emit_jump(OpCode.JUMP_IF_FALSE)
        self._emit_op(OpCode.POP)
        self._compile_stmt(stmt.body)
        self._emit_loop(loop_start)
        self._patch_jump(exit_jump)
        self._emit_op(OpCode.POP)

    def _stmt_FunctionStmt(self, stmt: ast.FunctionStmt) -> None:
        name = stmt.name.lexeme
        function = self._compile_function(stmt, name)
        index = self._chunk.add_constant(function)
        self._emit_op(OpCode.CONSTANT)
        self._emit(index)

        if self.current.scope_depth > 0:
            self._declare_local(name)
            self._mark_initialized()
        else:
            name_index = self._chunk.add_constant(name)
            self._emit_op(OpCode.DEFINE_GLOBAL)
            self._emit(name_index)

    def _compile_function(self, stmt: ast.FunctionStmt, name: str) -> QuillFunction:
        enclosing = self.current
        self.current = _FunctionState(enclosing, name, len(stmt.params))
        self._begin_scope()

        for param in stmt.params:
            self._declare_local(param.lexeme)
            self._mark_initialized()

        for s in stmt.body:
            self._compile_stmt(s)

        self._emit_return()
        function = self.current.function
        self.current = enclosing
        return function

    def _stmt_ReturnStmt(self, stmt: ast.ReturnStmt) -> None:
        if stmt.value is None:
            self._emit_op(OpCode.NIL)
        else:
            self._compile_expr(stmt.value)
        self._emit_op(OpCode.RETURN)

    # -- expressions -----------------------------------------------------------

    def _compile_expr(self, expr: ast.Expr) -> None:
        method = getattr(self, f"_expr_{type(expr).__name__}")
        method(expr)

    def _expr_Literal(self, expr: ast.Literal) -> None:
        if expr.value is True:
            self._emit_op(OpCode.TRUE)
        elif expr.value is False:
            self._emit_op(OpCode.FALSE)
        elif expr.value is None:
            self._emit_op(OpCode.NIL)
        else:
            self._emit_constant(expr.value)

    def _expr_Variable(self, expr: ast.Variable) -> None:
        name = expr.name.lexeme
        slot = self._resolve_local(self.current, name)
        if slot != -1:
            self._emit_op(OpCode.GET_LOCAL)
            self._emit(slot)
        else:
            index = self._chunk.add_constant(name)
            self._emit_op(OpCode.GET_GLOBAL)
            self._emit(index)

    def _expr_Assign(self, expr: ast.Assign) -> None:
        self._compile_expr(expr.value)
        name = expr.name.lexeme
        slot = self._resolve_local(self.current, name)
        if slot != -1:
            self._emit_op(OpCode.SET_LOCAL)
            self._emit(slot)
        else:
            index = self._chunk.add_constant(name)
            self._emit_op(OpCode.SET_GLOBAL)
            self._emit(index)

    def _expr_Unary(self, expr: ast.Unary) -> None:
        self._compile_expr(expr.right)
        if expr.operator.type == TokenType.MINUS:
            self._emit_op(OpCode.NEGATE)
        elif expr.operator.type == TokenType.BANG:
            self._emit_op(OpCode.NOT)

    def _expr_Binary(self, expr: ast.Binary) -> None:
        self._compile_expr(expr.left)
        self._compile_expr(expr.right)
        op_type = expr.operator.type
        if op_type == TokenType.BANG_EQUAL:
            self._emit_op(OpCode.EQUAL)
            self._emit_op(OpCode.NOT)
        elif op_type == TokenType.EQUAL_EQUAL:
            self._emit_op(OpCode.EQUAL)
        elif op_type == TokenType.GREATER_EQUAL:
            self._emit_op(OpCode.LESS)
            self._emit_op(OpCode.NOT)
        elif op_type == TokenType.LESS_EQUAL:
            self._emit_op(OpCode.GREATER)
            self._emit_op(OpCode.NOT)
        elif op_type in _BINARY_OPS:
            self._emit_op(_BINARY_OPS[op_type])
        else:  # pragma: no cover - unreachable given the parser's grammar
            raise CompileError(f"Unknown binary operator {expr.operator.lexeme!r}")

    def _expr_Logical(self, expr: ast.Logical) -> None:
        self._compile_expr(expr.left)
        if expr.operator.type == TokenType.AND:
            end_jump = self._emit_jump(OpCode.JUMP_IF_FALSE)
            self._emit_op(OpCode.POP)
            self._compile_expr(expr.right)
            self._patch_jump(end_jump)
        else:  # OR
            else_jump = self._emit_jump(OpCode.JUMP_IF_FALSE)
            end_jump = self._emit_jump(OpCode.JUMP)
            self._patch_jump(else_jump)
            self._emit_op(OpCode.POP)
            self._compile_expr(expr.right)
            self._patch_jump(end_jump)

    def _expr_Call(self, expr: ast.Call) -> None:
        self._compile_expr(expr.callee)
        for arg in expr.arguments:
            self._compile_expr(arg)
        self._emit_op(OpCode.CALL)
        self._emit(len(expr.arguments))


def compile_program(statements: List[ast.Stmt]) -> QuillFunction:
    return Compiler().compile(statements)
