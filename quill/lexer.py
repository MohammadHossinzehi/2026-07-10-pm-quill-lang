"""Hand-written lexer (tokenizer) for the Quill language.

Turns raw source text into a flat list of Token objects. Single pass,
no lookahead beyond one character, tracks line numbers for error
reporting.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, List


class TokenType(Enum):
    # Single-character tokens
    LEFT_PAREN = auto()
    RIGHT_PAREN = auto()
    LEFT_BRACE = auto()
    RIGHT_BRACE = auto()
    COMMA = auto()
    DOT = auto()
    MINUS = auto()
    PLUS = auto()
    SEMICOLON = auto()
    SLASH = auto()
    STAR = auto()

    # One or two character tokens
    BANG = auto()
    BANG_EQUAL = auto()
    EQUAL = auto()
    EQUAL_EQUAL = auto()
    GREATER = auto()
    GREATER_EQUAL = auto()
    LESS = auto()
    LESS_EQUAL = auto()

    # Literals
    IDENTIFIER = auto()
    STRING = auto()
    NUMBER = auto()

    # Keywords
    AND = auto()
    ELSE = auto()
    FALSE = auto()
    FUN = auto()
    FOR = auto()
    IF = auto()
    NIL = auto()
    OR = auto()
    PRINT = auto()
    RETURN = auto()
    TRUE = auto()
    VAR = auto()
    WHILE = auto()

    EOF = auto()


KEYWORDS = {
    "and": TokenType.AND,
    "else": TokenType.ELSE,
    "false": TokenType.FALSE,
    "for": TokenType.FOR,
    "fun": TokenType.FUN,
    "if": TokenType.IF,
    "nil": TokenType.NIL,
    "or": TokenType.OR,
    "print": TokenType.PRINT,
    "return": TokenType.RETURN,
    "true": TokenType.TRUE,
    "var": TokenType.VAR,
    "while": TokenType.WHILE,
}


@dataclass(frozen=True)
class Token:
    type: TokenType
    lexeme: str
    literal: Any
    line: int

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Token({self.type.name}, {self.lexeme!r}, {self.literal!r}, line={self.line})"


class LexError(Exception):
    """Raised when the source text contains characters that cannot be tokenized."""

    def __init__(self, message: str, line: int):
        super().__init__(f"[line {line}] Lex error: {message}")
        self.message = message
        self.line = line


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.tokens: List[Token] = []
        self.start = 0
        self.current = 0
        self.line = 1

    def scan_tokens(self) -> List[Token]:
        while not self._is_at_end():
            self.start = self.current
            self._scan_token()
        self.tokens.append(Token(TokenType.EOF, "", None, self.line))
        return self.tokens

    # -- helpers ---------------------------------------------------------

    def _is_at_end(self) -> bool:
        return self.current >= len(self.source)

    def _advance(self) -> str:
        char = self.source[self.current]
        self.current += 1
        return char

    def _peek(self) -> str:
        if self._is_at_end():
            return "\0"
        return self.source[self.current]

    def _peek_next(self) -> str:
        if self.current + 1 >= len(self.source):
            return "\0"
        return self.source[self.current + 1]

    def _match(self, expected: str) -> bool:
        if self._is_at_end() or self.source[self.current] != expected:
            return False
        self.current += 1
        return True

    def _add_token(self, type_: TokenType, literal: Any = None) -> None:
        text = self.source[self.start:self.current]
        self.tokens.append(Token(type_, text, literal, self.line))

    # -- scanning ----------------------------------------------------------

    def _scan_token(self) -> None:
        c = self._advance()

        simple = {
            "(": TokenType.LEFT_PAREN,
            ")": TokenType.RIGHT_PAREN,
            "{": TokenType.LEFT_BRACE,
            "}": TokenType.RIGHT_BRACE,
            ",": TokenType.COMMA,
            ".": TokenType.DOT,
            "-": TokenType.MINUS,
            "+": TokenType.PLUS,
            ";": TokenType.SEMICOLON,
            "*": TokenType.STAR,
        }

        if c in simple:
            self._add_token(simple[c])
        elif c == "!":
            self._add_token(TokenType.BANG_EQUAL if self._match("=") else TokenType.BANG)
        elif c == "=":
            self._add_token(TokenType.EQUAL_EQUAL if self._match("=") else TokenType.EQUAL)
        elif c == "<":
            self._add_token(TokenType.LESS_EQUAL if self._match("=") else TokenType.LESS)
        elif c == ">":
            self._add_token(TokenType.GREATER_EQUAL if self._match("=") else TokenType.GREATER)
        elif c == "/":
            if self._match("/"):
                while self._peek() != "\n" and not self._is_at_end():
                    self._advance()
            else:
                self._add_token(TokenType.SLASH)
        elif c in " \r\t":
            pass
        elif c == "\n":
            self.line += 1
        elif c == '"':
            self._string()
        elif c.isdigit():
            self._number()
        elif c.isalpha() or c == "_":
            self._identifier()
        else:
            raise LexError(f"Unexpected character {c!r}", self.line)

    def _string(self) -> None:
        while self._peek() != '"' and not self._is_at_end():
            if self._peek() == "\n":
                self.line += 1
            self._advance()

        if self._is_at_end():
            raise LexError("Unterminated string", self.line)

        self._advance()  # closing quote
        value = self.source[self.start + 1:self.current - 1]
        self._add_token(TokenType.STRING, value)

    def _number(self) -> None:
        while self._peek().isdigit():
            self._advance()

        is_float = False
        if self._peek() == "." and self._peek_next().isdigit():
            is_float = True
            self._advance()
            while self._peek().isdigit():
                self._advance()

        text = self.source[self.start:self.current]
        value = float(text) if is_float else int(text)
        self._add_token(TokenType.NUMBER, value)

    def _identifier(self) -> None:
        while self._peek().isalnum() or self._peek() == "_":
            self._advance()
        text = self.source[self.start:self.current]
        type_ = KEYWORDS.get(text, TokenType.IDENTIFIER)
        self._add_token(type_)


def tokenize(source: str) -> List[Token]:
    return Lexer(source).scan_tokens()
