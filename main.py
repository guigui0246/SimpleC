from __future__ import annotations

import argparse
from pathlib import Path

from ast_to_bytecode import compile_program
from code_to_ast import parse_file
from run_bytecode import VirtualMachine, load_bytecode, save_bytecode


def cmd_parse(source: Path) -> None:
    ast = parse_file(source)
    print(ast)


def cmd_compile(source: Path, output: Path) -> None:
    ast = parse_file(source)
    bytecode = compile_program(ast)
    save_bytecode(bytecode, output)
    print(f"Bytecode saved to: {output}")


def cmd_run(source: Path) -> None:
    ast = parse_file(source)
    bytecode = compile_program(ast)
    vm = VirtualMachine()
    vm.run(bytecode)


def cmd_run_bytecode(input_path: Path) -> None:
    bytecode = load_bytecode(input_path)
    vm = VirtualMachine()
    vm.run(bytecode)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SimpleC Python compiler and bytecode VM")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_parser = subparsers.add_parser("parse", help="Parse source code and print AST")
    parse_parser.add_argument("source", type=Path, help="Source .sc file")

    compile_parser = subparsers.add_parser("compile", help="Compile source file to bytecode")
    compile_parser.add_argument("source", type=Path, help="Source .sc file")
    compile_parser.add_argument("-o", "--output", type=Path, required=True, help="Output bytecode file")

    run_parser = subparsers.add_parser("run", help="Parse + compile + execute source file")
    run_parser.add_argument("source", type=Path, help="Source .sc file")

    run_bc_parser = subparsers.add_parser("run-bytecode", help="Load and execute saved bytecode")
    run_bc_parser.add_argument("input", type=Path, help="Input bytecode file")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "parse":
        cmd_parse(args.source)
        return

    if args.command == "compile":
        cmd_compile(args.source, args.output)
        return

    if args.command == "run":
        cmd_run(args.source)
        return

    if args.command == "run-bytecode":
        cmd_run_bytecode(args.input)
        return

    raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
