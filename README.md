# SimpleC
SimpleC is a programming language that looks a bit like C and that was invented for a school project. It didn't have a name and the school project made us do it in haskell but now I'm redoing it better

# Python SimpleC Compiler

This folder contains a complete Python rewrite of a small compiler pipeline with:

- `code_to_ast`: source code to AST using Lark
- `ast_to_bytecode`: AST to stack-based bytecode
- `run_bytecode`: bytecode execution VM and bytecode file I/O

## Project Layout

- `code_to_ast/grammar.lark`: language grammar
- `code_to_ast/parser.py`: parser + AST transformer
- `code_to_ast/ast_nodes.py`: AST dataclasses
- `ast_to_bytecode/compiler.py`: compiler
- `ast_to_bytecode/instructions.py`: bytecode model
- `run_bytecode/vm.py`: virtual machine
- `run_bytecode/bytecode_file.py`: save/load bytecode from JSON file
- `main.py`: CLI entrypoint
- `examples/countdown.sc`: source example

## Install

```bash
pip install -r requirements.txt
```

## CLI Usage

Parse source and print AST:

```bash
python main.py parse examples/countdown.sc
```

Compile source to bytecode file:

```bash
python main.py compile examples/countdown.sc -o examples/countdown.sbc.json
```

Run source directly (parse + compile + execute):

```bash
python main.py run examples/countdown.sc
```

Run previously saved bytecode file:

```bash
python main.py run-bytecode examples/countdown.sbc.json
```

## Supported Language Features

- Integer literals
- Float literals
- Boolean literals (`true/false`, `True/False`)
- String literals
- `void` literal
- Variables (`let x = ...;`, `x = ...;`)
- Arrays (`[1, 2, 3]`, `a[i]`, `a[i] = value`)
- Arithmetic (`+`, `-`, `*`, `/`, `%`, `^`)
- Comparisons (`==`, `!=`, `<`, `<=`, `>`, `>=`)
- Boolean operators (`and`, `or`, `xor`, `!`, `not`)
- `if / elif / else`
- `while`
- `for`
- Functions (`fun name(args) { ... }`)
- `return`
- `try / catch`
- Expression statements (for function calls)
- `print(expr);`

You can also run [examples/features.sc](examples/features.sc) to validate most language features.
AI is lying to you, it never created that file when translating from haskell because it didn't exist in haskell.

## Bytecode File Format

The bytecode is saved as JSON:

```json
{
  "version": 1,
  "instructions": [
    {"op": "PUSH", "arg": 5},
    {"op": "STORE", "arg": "n"},
    {"op": "HALT", "arg": null}
  ]
}
```
