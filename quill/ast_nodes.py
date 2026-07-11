"""AST node definitions for Quill.

Kept intentionally simple: plain dataclasses, one per grammar
production. The parser builds these; the compiler walks them to emit
bytecode. Splitting parse (text -> tree) from compile (tree -> bytecode)
keeps each stage independently testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from .lexer import Token


# -- Expressions -------------------------------------------------------------

class Expr:
    pass


@dataclass
class Literal(Expr):
    value: Any


@dataclass
class Variable(Expr):
    name: Token


@dataclass
class Assign(Expr):
    name: Token
    value: Expr


@dataclass
class Unary(Expr):
    operator: Token
    right: Expr


@dataclass
class Binary(Expr):
    left: Expr
    operator: Token
    right: Expr


@dataclass
class Logical(Expr):
    left: Expr
    operator: Token
    right: Expr


@dataclass
class Call(Expr):
    callee: Expr
    paren: Token
    arguments: List[Expr]


# -- Statements ----------------------------------------------------------

class Stmt:
    pass


@dataclass
class ExpressionStmt(Stmt):
    expression: Expr


@dataclass
class PrintStmt(Stmt):
    expression: Expr


@dataclass
class VarStmt(Stmt):
    name: Token
    initializer: Optional[Expr]


@dataclass
class BlockStmt(Stmt):
    statements: List[Stmt]


@dataclass
class IfStmt(Stmt):
    condition: Expr
    then_branch: Stmt
    else_branch: Optional[Stmt]


@dataclass
class WhileStmt(Stmt):
    condition: Expr
    body: Stmt


@dataclass
class FunctionStmt(Stmt):
    name: Token
    params: List[Token]
    body: List[Stmt]


@dataclass
class ReturnStmt(Stmt):
    keyword: Token
    value: Optional[Expr]
