# Quill

A small dynamically typed scripting language with a real pipeline: a
hand-written lexer, a recursive-descent parser, a compiler that emits
stack-based bytecode, and a virtual machine that executes it. Every
stage is implemented from scratch in pure Python, with no third-party
dependencies.

```
source text -> Lexer -> tokens -> Parser -> AST -> Compiler -> bytecode -> VM -> output
```

## Why this exists

Most people use a language every day without ever seeing how one is
built. This project is a compact, readable implementation of the same
pipeline production language runtimes use (roughly the design of
`clox` from *Crafting Interpreters*, reimplemented independently in
Python): tokenize, parse into a tree, compile the tree down to a flat
instruction stream, then run that instruction stream on a stack
machine instead of walking the tree at runtime. It's meant to be
readable end to end in one sitting, while still being a genuinely
working language: it has variables, functions, recursion (but not closures - see
Design decisions), control flow, and a REPL.

## What Quill can do

- Numbers (int and float), strings, booleans, and `nil`
- Arithmetic (`+ - * /`), comparisons (`== != < <= > >=`), and logical
  `and` / `or` with short-circuit evaluation
- `var` declarations, assignment, and lexically scoped blocks (`{ }`)
  with correct shadowing
- `if` / `else`, `while`, and `for` (desugared to `while` in the parser)
- `fun` declarations, function calls, and recursion (including mutual
  recursion through globals)
- A `print` statement and one native function, `clock()`
- A REPL and a script runner
- A bytecode disassembler for inspecting exactly what the compiler emits

## Quickstart

Requires Python 3.8+. No dependencies to install.

```bash
# Run a script
python cli.py examples/fib.ql

# Start the REPL
python cli.py

# See the bytecode the compiler generates for a script
python disassemble.py examples/factorial.ql

# Run the test suite
python -m unittest discover -s tests -v
```

Example session:

```
$ python cli.py
Quill REPL (Python 3.11.4) - Ctrl-D to exit
quill> fun add(a, b) { return a + b; }
quill> print add(2, 3);
5
quill> var i = 0; while (i < 3) { print i; i = i + 1; }
0
1
2
```

## Project structure

```
quill/
  lexer.py        Tokenizer: source text -> list of Tokens
  ast_nodes.py     AST node dataclasses (Expr and Stmt subclasses)
  parser.py        Recursive-descent parser: tokens -> AST
  chunk.py         OpCode enum + Chunk (bytecode + constants container)
  compiler.py      AST -> bytecode, one Chunk per function, scope/local
                   resolution done entirely at compile time
  objects.py       Runtime object types (QuillFunction, NativeFunction)
  vm.py            The stack machine: CallFrame stack + dispatch loop
  interpreter.py   Glue: wires lexer/parser/compiler/vm together
cli.py             Script runner + REPL entry point
disassemble.py     Standalone bytecode disassembler
examples/          Sample .ql scripts (fibonacci, loops/scope, factorial)
tests/             unittest suite: lexer, parser, and end-to-end VM tests
```

## Design decisions

**Two-stage compile, not single-pass.** clox parses and emits bytecode
in one pass with a Pratt parser. Quill splits that into a parser that
builds a real AST and a separate compiler that walks it. This costs a
small amount of performance (an extra tree allocation) but makes each
stage independently testable: `tests/test_parser.py` checks tree shape
without touching bytecode at all, and `tests/test_interpreter.py`
checks end-to-end behavior without caring how the tree got built.

**Locals resolved at compile time, globals resolved by name at
runtime.** Every local variable is assigned a fixed stack slot index
during compilation (see `Compiler._resolve_local`), so reading or
writing a local is a single array index at runtime with no lookup.
Globals go through a name-keyed dict on the VM (`OP_GET_GLOBAL` /
`OP_SET_GLOBAL` / `OP_DEFINE_GLOBAL`), which is slower but far simpler,
matching how `clox` itself treats the two cases differently.

**No closures.** Functions can read their own parameters and locals
and any global, but cannot capture a variable from an *enclosing
function's* local scope (no upvalues). Implementing that correctly
(open/closed upvalues, capturing by reference vs. value) is one of the
more delicate parts of a real language VM, and was cut deliberately to
keep this implementation small enough to read in one sitting rather
than half-implemented and subtly wrong. Top-level functions calling
each other (including mutual recursion) work fine, since that only
needs globals. This is called out explicitly rather than glossed over.

**`for` desugars into `while` in the parser**, not the compiler,
following the same trick jlox/clox use: fewer bytecode ops to
implement and test, at the cost of the parser producing a slightly
less literal tree for `for` loops (see
`test_for_loop_desugars_to_while`).

**Jump patching.** `if`/`while`/`and`/`or` all compile down to
`OP_JUMP`, `OP_JUMP_IF_FALSE`, and `OP_LOOP` with backpatched offsets:
the compiler emits a placeholder operand, keeps its index, and patches
in the real offset once the jump target is known (`_emit_jump` /
`_patch_jump` in `compiler.py`). This is the standard technique for
emitting forward jumps in a single linear pass without a separate
control-flow graph.

## Testing

38 unit tests across three files, run with the standard library's
`unittest` (no test framework dependency):

- `tests/test_lexer.py` - token types, literal values (int vs. float),
  string handling, comments, line tracking, and lex errors
- `tests/test_parser.py` - AST shape for declarations, precedence,
  control flow, function declarations, and parse errors (missing
  semicolon, invalid assignment target)
- `tests/test_interpreter.py` - end-to-end program behavior: the VM is
  given an injectable `print_fn` so tests assert on captured output
  instead of scraping stdout. Covers arithmetic, string concatenation,
  comparisons, scoping/shadowing, all control flow, recursion
  (Fibonacci, factorial), mutual recursion, wrong-arity call errors,
  division by zero, and type errors on `+`

Run them with:

```bash
python -m unittest discover -s tests -v
```

## Known limitations

- No closures over enclosing function locals (see Design decisions)
- No classes/objects, arrays, or hash maps - only numbers, strings,
  booleans, `nil`, and functions
- Runtime error messages don't yet carry the original Quill source
  line number (lex and parse errors do; a runtime `QuillRuntimeError`
  currently reports the problem without a line, which would be the
  natural next thing to fix by threading line numbers from the AST
  through the compiler's `_emit` calls)
- No garbage collector needed or implemented: the VM relies entirely
  on Python's own memory management for every runtime value
