"""Recursive-descent parser for Quill.

Grammar (roughly, in precedence order for expressions):

    program     -> declaration* EOF
    declaration -> funDecl | varDecl | statement
    funDecl     -> "fun" IDENTIFIER "(" params? ")" block
    varDecl     -> "var" IDENTIFIER ( "=" expression )? ";"
    statement   -> exprStmt | ifStmt | printStmt | returnStmt
                 | whileStmt | forStmt | block
    forStmt     -> "for" "(" (varDecl|exprStmt|";") expression? ";" expression? ")" statement
    block       -> "{" declaration* "}"
    expression  -> assignment
    assignment  -> IDENTIFIER "=" assignment | logic_or
    logic_or    -> logic_and ( "or" logic_and )*
    logic_and   -> equality ( "and" equality )*
    equality    -> comparison ( ( "!=" | "==" ) comparison )*
    comparison  -> term ( ( ">" | ">=" | "<" | "<=" ) term )*
    term        -> factor ( ( "-" | "+" ) factor )*
    factor      -> unary ( ( "/" | "*" ) unary )*
    unary       -> ( "!" | "-" ) unary | call
    call        -> primary ( "(" arguments? ")" )*
    primary     -> NUMBER | STRING | "true" | "false" | "nil"
                 | "(" expression ")" | IDENTIFIER
"""

from __future__ import annotations

from typing import List, Optional

from .ast_nodes import (
    Assign, Binary, BlockStmt, Call, Expr, ExpressionStmt, FunctionStmt,
    IfStmt, Literal, Logical, PrintStmt, ReturnStmt, Stmt, Unary, VarStmt,
    Variable, WhileStmt,
)
from .lexer import Token, TokenType


class ParseError(Exception):
    def __init__(self, message: str, token: Token):
        where = "end" if token.type == TokenType.EOF else repr(token.lexeme)
        super().__init__(f"[line {token.line}] Parse error at {where}: {message}")
        self.token = token


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.current = 0

    def parse(self) -> List[Stmt]:
        statements = []
        while not self._is_at_end():
            statements.append(self._declaration())
        return statements

    # -- declarations ------------------------------------------------------

    def _declaration(self) -> Stmt:
        if self._match(TokenType.FUN):
            return self._function("function")
        if self._match(TokenType.VAR):
            return self._var_declaration()
        return self._statement()

    def _function(self, kind: str) -> FunctionStmt:
        name = self._consume(TokenType.IDENTIFIER, f"Expect {kind} name.")
        self._consume(TokenType.LEFT_PAREN, f"Expect '(' after {kind} name.")
        params: List[Token] = []
        if not self._check(TokenType.RIGHT_PAREN):
            while True:
                if len(params) >= 255:
                    raise ParseError("Can't have more than 255 parameters.", self._peek())
                params.append(self._consume(TokenType.IDENTIFIER, "Expect parameter name."))
                if not self._match(TokenType.COMMA):
                    break
        self._consume(TokenType.RIGHT_PAREN, "Expect ')' after parameters.")
        self._consume(TokenType.LEFT_BRACE, f"Expect '{{' before {kind} body.")
        body = self._block()
        return FunctionStmt(name, params, body)

    def _var_declaration(self) -> VarStmt:
        name = self._consume(TokenType.IDENTIFIER, "Expect variable name.")
        initializer = None
        if self._match(TokenType.EQUAL):
            initializer = self._expression()
        self._consume(TokenType.SEMICOLON, "Expect ';' after variable declaration.")
        return VarStmt(name, initializer)

    # -- statements ----------------------------------------------------------

    def _statement(self) -> Stmt:
        if self._match(TokenType.IF):
            return self._if_statement()
        if self._match(TokenType.PRINT):
            return self._print_statement()
        if self._match(TokenType.RETURN):
            return self._return_statement()
        if self._match(TokenType.WHILE):
            return self._while_statement()
        if self._match(TokenType.FOR):
            return self._for_statement()
        if self._match(TokenType.LEFT_BRACE):
            return BlockStmt(self._block())
        return self._expression_statement()

    def _if_statement(self) -> IfStmt:
        self._consume(TokenType.LEFT_PAREN, "Expect '(' after 'if'.")
        condition = self._expression()
        self._consume(TokenType.RIGHT_PAREN, "Expect ')' after if condition.")
        then_branch = self._statement()
        else_branch = self._statement() if self._match(TokenType.ELSE) else None
        return IfStmt(condition, then_branch, else_branch)

    def _print_statement(self) -> PrintStmt:
        value = self._expression()
        self._consume(TokenType.SEMICOLON, "Expect ';' after value.")
        return PrintStmt(value)

    def _return_statement(self) -> ReturnStmt:
        keyword = self._previous()
        value = None
        if not self._check(TokenType.SEMICOLON):
            value = self._expression()
        self._consume(TokenType.SEMICOLON, "Expect ';' after return value.")
        return ReturnStmt(keyword, value)

    def _while_statement(self) -> WhileStmt:
        self._consume(TokenType.LEFT_PAREN, "Expect '(' after 'while'.")
        condition = self._expression()
        self._consume(TokenType.RIGHT_PAREN, "Expect ')' after condition.")
        body = self._statement()
        return WhileStmt(condition, body)

    def _for_statement(self) -> Stmt:
        # Desugars into a while loop wrapped in a block, same trick as clox/jlox.
        self._consume(TokenType.LEFT_PAREN, "Expect '(' after 'for'.")

        if self._match(TokenType.SEMICOLON):
            initializer: Optional[Stmt] = None
        elif self._match(TokenType.VAR):
            initializer = self._var_declaration()
        else:
            initializer = self._expression_statement()

        condition = None
        if not self._check(TokenType.SEMICOLON):
            condition = self._expression()
        self._consume(TokenType.SEMICOLON, "Expect ';' after loop condition.")

        increment = None
        if not self._check(TokenType.RIGHT_PAREN):
            increment = self._expression()
        self._consume(TokenType.RIGHT_PAREN, "Expect ')' after for clauses.")

        body = self._statement()

        if increment is not None:
            body = BlockStmt([body, ExpressionStmt(increment)])

        if condition is None:
            condition = Literal(True)
        body = WhileStmt(condition, body)

        if initializer is not None:
            body = BlockStmt([initializer, body])

        return body

    def _block(self) -> List[Stmt]:
        statements = []
        while not self._check(TokenType.RIGHT_BRACE) and not self._is_at_end():
            statements.append(self._declaration())
        self._consume(TokenType.RIGHT_BRACE, "Expect '}' after block.")
        return statements

    def _expression_statement(self) -> ExpressionStmt:
        expr = self._expression()
        self._consume(TokenType.SEMICOLON, "Expect ';' after expression.")
        return ExpressionStmt(expr)

    # -- expressions ---------------------------------------------------------

    def _expression(self) -> Expr:
        return self._assignment()

    def _assignment(self) -> Expr:
        expr = self._or()

        if self._match(TokenType.EQUAL):
            equals = self._previous()
            value = self._assignment()
            if isinstance(expr, Variable):
                return Assign(expr.name, value)
            raise ParseError("Invalid assignment target.", equals)

        return expr

    def _or(self) -> Expr:
        expr = self._and()
        while self._match(TokenType.OR):
            operator = self._previous()
            right = self._and()
            expr = Logical(expr, operator, right)
        return expr

    def _and(self) -> Expr:
        expr = self._equality()
        while self._match(TokenType.AND):
            operator = self._previous()
            right = self._equality()
            expr = Logical(expr, operator, right)
        return expr

    def _equality(self) -> Expr:
        expr = self._comparison()
        while self._match(TokenType.BANG_EQUAL, TokenType.EQUAL_EQUAL):
            operator = self._previous()
            right = self._comparison()
            expr = Binary(expr, operator, right)
        return expr

    def _comparison(self) -> Expr:
        expr = self._term()
        while self._match(TokenType.GREATER, TokenType.GREATER_EQUAL,
                           TokenType.LESS, TokenType.LESS_EQUAL):
            operator = self._previous()
            right = self._term()
            expr = Binary(expr, operator, right)
        return expr

    def _term(self) -> Expr:
        expr = self._factor()
        while self._match(TokenType.MINUS, TokenType.PLUS):
            operator = self._previous()
            right = self._factor()
            expr = Binary(expr, operator, right)
        return expr

    def _factor(self) -> Expr:
        expr = self._unary()
        while self._match(TokenType.SLASH, TokenType.STAR):
            operator = self._previous()
            right = self._unary()
            expr = Binary(expr, operator, right)
        return expr

    def _unary(self) -> Expr:
        if self._match(TokenType.BANG, TokenType.MINUS):
            operator = self._previous()
            right = self._unary()
            return Unary(operator, right)
        return self._call()

    def _call(self) -> Expr:
        expr = self._primary()
        while True:
            if self._match(TokenType.LEFT_PAREN):
                expr = self._finish_call(expr)
            else:
                break
        return expr

    def _finish_call(self, callee: Expr) -> Expr:
        arguments = []
        if not self._check(TokenType.RIGHT_PAREN):
            while True:
                if len(arguments) >= 255:
                    raise ParseError("Can't have more than 255 arguments.", self._peek())
                arguments.append(self._expression())
                if not self._match(TokenType.COMMA):
                    break
        paren = self._consume(TokenType.RIGHT_PAREN, "Expect ')' after arguments.")
        return Call(callee, paren, arguments)

    def _primary(self) -> Expr:
        if self._match(TokenType.FALSE):
            return Literal(False)
        if self._match(TokenType.TRUE):
            return Literal(True)
        if self._match(TokenType.NIL):
            return Literal(None)
        if self._match(TokenType.NUMBER, TokenType.STRING):
            return Literal(self._previous().literal)
        if self._match(TokenType.IDENTIFIER):
            return Variable(self._previous())
        if self._match(TokenType.LEFT_PAREN):
            expr = self._expression()
            self._consume(TokenType.RIGHT_PAREN, "Expect ')' after expression.")
            return expr
        raise ParseError("Expect expression.", self._peek())

    # -- token stream helpers ------------------------------------------------

    def _match(self, *types: TokenType) -> bool:
        for type_ in types:
            if self._check(type_):
                self._advance()
                return True
        return False

    def _check(self, type_: TokenType) -> bool:
        if self._is_at_end():
            return False
        return self._peek().type == type_

    def _advance(self) -> Token:
        if not self._is_at_end():
            self.current += 1
        return self._previous()

    def _is_at_end(self) -> bool:
        return self._peek().type == TokenType.EOF

    def _peek(self) -> Token:
        return self.tokens[self.current]

    def _previous(self) -> Token:
        return self.tokens[self.current - 1]

    def _consume(self, type_: TokenType, message: str) -> Token:
        if self._check(type_):
            return self._advance()
        raise ParseError(message, self._peek())


def parse(tokens: List[Token]) -> List[Stmt]:
    return Parser(tokens).parse()
