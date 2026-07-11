import unittest

from quill.interpreter import QuillError, run_source


def run_and_capture(source: str):
    output = []
    run_source(source, print_fn=output.append)
    return output


class ArithmeticTests(unittest.TestCase):
    def test_basic_arithmetic(self):
        self.assertEqual(run_and_capture("print 1 + 2 * 3;"), ["7"])
        self.assertEqual(run_and_capture("print (1 + 2) * 3;"), ["9"])
        self.assertEqual(run_and_capture("print 10 / 4;"), ["2.5"])
        self.assertEqual(run_and_capture("print 2 - 3;"), ["-1"])

    def test_string_concatenation(self):
        self.assertEqual(run_and_capture('print "foo" + "bar";'), ["foobar"])

    def test_comparisons(self):
        self.assertEqual(run_and_capture("print 1 < 2;"), ["true"])
        self.assertEqual(run_and_capture("print 1 >= 2;"), ["false"])
        self.assertEqual(run_and_capture("print 3 == 3;"), ["true"])
        self.assertEqual(run_and_capture("print 3 != 3;"), ["false"])

    def test_negation_and_not(self):
        self.assertEqual(run_and_capture("print -5;"), ["-5"])
        self.assertEqual(run_and_capture("print !true;"), ["false"])
        self.assertEqual(run_and_capture("print !false;"), ["true"])

    def test_division_by_zero_raises(self):
        with self.assertRaises(QuillError):
            run_and_capture("print 1 / 0;")

    def test_adding_number_and_string_raises(self):
        with self.assertRaises(QuillError):
            run_and_capture('print 1 + "a";')


class VariableAndScopeTests(unittest.TestCase):
    def test_global_variable(self):
        self.assertEqual(run_and_capture("var x = 10; print x;"), ["10"])

    def test_assignment(self):
        self.assertEqual(run_and_capture("var x = 1; x = 2; print x;"), ["2"])

    def test_block_scoping_shadows(self):
        source = """
        var x = "outer";
        {
          var x = "inner";
          print x;
        }
        print x;
        """
        self.assertEqual(run_and_capture(source), ["inner", "outer"])

    def test_undefined_variable_raises(self):
        with self.assertRaises(QuillError):
            run_and_capture("print undefined_name;")


class ControlFlowTests(unittest.TestCase):
    def test_if_else(self):
        self.assertEqual(run_and_capture('if (1 < 2) { print "yes"; } else { print "no"; }'),
                          ["yes"])

    def test_while_loop(self):
        source = """
        var i = 0;
        var sum = 0;
        while (i < 5) {
          sum = sum + i;
          i = i + 1;
        }
        print sum;
        """
        self.assertEqual(run_and_capture(source), ["10"])

    def test_for_loop(self):
        source = """
        var total = 0;
        for (var i = 1; i <= 5; i = i + 1) {
          total = total + i;
        }
        print total;
        """
        self.assertEqual(run_and_capture(source), ["15"])

    def test_and_or_short_circuit(self):
        source = """
        fun sideeffect() { print "called"; return true; }
        print false and sideeffect();
        print true or sideeffect();
        """
        # Neither branch should call sideeffect() because both
        # short-circuit before evaluating the right operand.
        self.assertEqual(run_and_capture(source), ["false", "true"])


class FunctionTests(unittest.TestCase):
    def test_simple_function(self):
        source = 'fun add(a, b) { return a + b; } print add(2, 3);'
        self.assertEqual(run_and_capture(source), ["5"])

    def test_recursive_fibonacci(self):
        source = """
        fun fib(n) {
          if (n < 2) { return n; }
          return fib(n - 1) + fib(n - 2);
        }
        print fib(10);
        """
        self.assertEqual(run_and_capture(source), ["55"])

    def test_recursive_factorial(self):
        source = """
        fun fact(n) {
          if (n <= 1) { return 1; }
          return n * fact(n - 1);
        }
        print fact(6);
        """
        self.assertEqual(run_and_capture(source), ["720"])

    def test_function_without_return_yields_nil(self):
        source = "fun noop() {} print noop();"
        self.assertEqual(run_and_capture(source), ["nil"])

    def test_wrong_arity_raises(self):
        with self.assertRaises(QuillError):
            run_and_capture("fun add(a, b) { return a + b; } print add(1);")

    def test_mutual_recursion_via_globals(self):
        source = """
        fun is_even(n) {
          if (n == 0) { return true; }
          return is_odd(n - 1);
        }
        fun is_odd(n) {
          if (n == 0) { return false; }
          return is_even(n - 1);
        }
        print is_even(10);
        print is_odd(10);
        """
        self.assertEqual(run_and_capture(source), ["true", "false"])


class NativeFunctionTests(unittest.TestCase):
    def test_clock_returns_number(self):
        self.assertEqual(run_and_capture("print clock() > 0;"), ["true"])


if __name__ == "__main__":
    unittest.main()
