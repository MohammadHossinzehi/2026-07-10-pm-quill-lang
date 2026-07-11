import unittest

from quill.lexer import LexError, TokenType, tokenize


class LexerTests(unittest.TestCase):
    def test_single_char_tokens(self):
        tokens = tokenize("(){},.-+;*")
        types = [t.type for t in tokens]
        self.assertEqual(types, [
            TokenType.LEFT_PAREN, TokenType.RIGHT_PAREN, TokenType.LEFT_BRACE,
            TokenType.RIGHT_BRACE, TokenType.COMMA, TokenType.DOT,
            TokenType.MINUS, TokenType.PLUS, TokenType.SEMICOLON,
            TokenType.STAR, TokenType.EOF,
        ])

    def test_two_char_operators(self):
        tokens = tokenize("!= == <= >= < > = !")
        types = [t.type for t in tokens]
        self.assertEqual(types, [
            TokenType.BANG_EQUAL, TokenType.EQUAL_EQUAL, TokenType.LESS_EQUAL,
            TokenType.GREATER_EQUAL, TokenType.LESS, TokenType.GREATER,
            TokenType.EQUAL, TokenType.BANG, TokenType.EOF,
        ])

    def test_numbers_int_and_float(self):
        tokens = tokenize("42 3.14")
        self.assertEqual(tokens[0].literal, 42)
        self.assertIsInstance(tokens[0].literal, int)
        self.assertEqual(tokens[1].literal, 3.14)
        self.assertIsInstance(tokens[1].literal, float)

    def test_string_literal(self):
        tokens = tokenize('"hello world"')
        self.assertEqual(tokens[0].type, TokenType.STRING)
        self.assertEqual(tokens[0].literal, "hello world")

    def test_unterminated_string_raises(self):
        with self.assertRaises(LexError):
            tokenize('"unterminated')

    def test_keywords_vs_identifiers(self):
        tokens = tokenize("var x = fun y")
        types = [t.type for t in tokens]
        self.assertEqual(types[0], TokenType.VAR)
        self.assertEqual(types[1], TokenType.IDENTIFIER)
        self.assertEqual(types[3], TokenType.FUN)

    def test_comments_are_skipped(self):
        tokens = tokenize("var x = 1; // this is a comment\nvar y = 2;")
        # No STRING/garbage tokens leak in from the comment.
        lexemes = [t.lexeme for t in tokens]
        self.assertNotIn("this", lexemes)

    def test_line_tracking(self):
        tokens = tokenize("var x = 1;\nvar y = 2;")
        y_token = next(t for t in tokens if t.lexeme == "y")
        self.assertEqual(y_token.line, 2)

    def test_unexpected_character_raises(self):
        with self.assertRaises(LexError):
            tokenize("var x = @;")


if __name__ == "__main__":
    unittest.main()
