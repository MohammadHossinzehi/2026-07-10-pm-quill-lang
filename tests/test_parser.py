import unittest

from quill import ast_nodes as ast
from quill.lexer import tokenize
from quill.parser import ParseError, parse


class ParserTests(unittest.TestCase):
    def test_var_declaration(self):
        stmts = parse(tokenize("var x = 1 + 2;"))
        self.assertEqual(len(stmts), 1)
        stmt = stmts[0]
        self.assertIsInstance(stmt, ast.VarStmt)
        self.assertEqual(stmt.name.lexeme, "x")
        self.assertIsInstance(stmt.initializer, ast.Binary)

    def test_precedence_multiplication_before_addition(self):
        stmts = parse(tokenize("print 1 + 2 * 3;"))
        expr = stmts[0].expression
        self.assertIsInstance(expr, ast.Binary)
        self.assertEqual(expr.operator.lexeme, "+")
        self.assertIsInstance(expr.right, ast.Binary)
        self.assertEqual(expr.right.operator.lexeme, "*")

    def test_if_else(self):
        stmts = parse(tokenize("if (true) { print 1; } else { print 2; }"))
        stmt = stmts[0]
        self.assertIsInstance(stmt, ast.IfStmt)
        self.assertIsInstance(stmt.then_branch, ast.BlockStmt)
        self.assertIsNotNone(stmt.else_branch)

    def test_function_declaration(self):
        stmts = parse(tokenize("fun add(a, b) { return a + b; }"))
        stmt = stmts[0]
        self.assertIsInstance(stmt, ast.FunctionStmt)
        self.assertEqual(stmt.name.lexeme, "add")
        self.assertEqual([p.lexeme for p in stmt.params], ["a", "b"])
        self.assertEqual(len(stmt.body), 1)
        self.assertIsInstance(stmt.body[0], ast.ReturnStmt)

    def test_call_expression(self):
        stmts = parse(tokenize("print add(1, 2);"))
        expr = stmts[0].expression
        self.assertIsInstance(expr, ast.Call)
        self.assertEqual(len(expr.arguments), 2)

    def test_for_loop_desugars_to_while(self):
        stmts = parse(tokenize("for (var i = 0; i < 3; i = i + 1) print i;"))
        # The for-loop is desugared into a block containing the
        # initializer followed by a while loop.
        self.assertIsInstance(stmts[0], ast.BlockStmt)
        inner = stmts[0].statements
        self.assertIsInstance(inner[0], ast.VarStmt)
        self.assertIsInstance(inner[1], ast.WhileStmt)

    def test_missing_semicolon_raises_parse_error(self):
        with self.assertRaises(ParseError):
            parse(tokenize("var x = 1"))

    def test_invalid_assignment_target_raises(self):
        with self.assertRaises(ParseError):
            parse(tokenize("1 + 2 = 3;"))


if __name__ == "__main__":
    unittest.main()
