from __future__ import annotations

import argparse
from pathlib import Path
from ast_to_bytecode import compile_program, Bytecode
from code_to_ast import parse_file, parse_code
from run_bytecode import VirtualMachine, load_bytecode, save_bytecode


def cmd_parse(source: Path) -> None:
    ast = parse_file(source)
    print(ast)


def cmd_compile(source: Path, output: Path) -> None:
    ast = parse_file(source)
    bytecode = compile_program(ast)
    save_bytecode(bytecode, output)
    print(f"Bytecode saved to: {output}")


def cmd_run(sources: list[Path]) -> None:
    bytecodes: dict[str, Bytecode] = {}
    for source in sources:
        ast = parse_file(source)
        program_bytecode = compile_program(ast)
        bytecodes[source.name] = program_bytecode
    bytecode = Bytecode([], {})
    funct_origin: dict[str, list[str]] = {}
    for source in sources:
        program_bytecode = bytecodes[source.name]
        for func_name in program_bytecode.functions:
            funct_origin.setdefault(func_name, []).append(source.name)
        bytecode.functions.update(program_bytecode.functions)
        bytecode.instructions.extend(program_bytecode.instructions)
    if any(len(sources) > 1 for sources in funct_origin.values()):
        error_messages = []
        for func_name, source_names in funct_origin.items():
            if len(source_names) > 1:
                error_messages.append(f"Function name conflict for '{func_name}' in files: {', '.join(source_names)}")
        raise ValueError("\n".join(error_messages))

    vm = VirtualMachine()
    print(vm.run(bytecode))


def cmd_run_bytecode(input_paths: list[Path]) -> None:
    bytecodes: dict[str, Bytecode] = {}
    for input_path in input_paths:
        bytecode = load_bytecode(input_path)
        bytecodes[input_path.name] = bytecode
    bytecode = Bytecode([], {})
    funct_origin: dict[str, list[str]] = {}
    for input_path in input_paths:
        program_bytecode = bytecodes[input_path.name]
        for func_name in program_bytecode.functions:
            funct_origin.setdefault(func_name, []).append(input_path.name)
        bytecode.functions.update(program_bytecode.functions)
        bytecode.instructions.extend(program_bytecode.instructions)
    if any(len(input_path_names) > 1 for input_path_names in funct_origin.values()):
        error_messages = []
        for func_name, input_path_names in funct_origin.items():
            if len(input_path_names) > 1:
                error_messages.append(f"Function name conflict for '{func_name}' in files: {', '.join(input_path_names)}")
        raise ValueError("\n".join(error_messages))

    vm = VirtualMachine()
    print(vm.run(bytecode))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SimpleC Python compiler and bytecode VM")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_parser = subparsers.add_parser("parse", help="Parse source code and print AST")
    parse_parser.add_argument("source", type=Path, help="Source .sc file")

    compile_parser = subparsers.add_parser("compile", help="Compile source file to bytecode")
    compile_parser.add_argument("source", type=Path, help="Source .sc file")
    compile_parser.add_argument("-o", "--output", type=Path, required=True, help="Output bytecode file")

    run_parser = subparsers.add_parser("run", help="Parse + compile + execute source file")
    run_parser.add_argument("source", type=Path, help="Source .sc file", nargs="+")

    run_bc_parser = subparsers.add_parser("run-bytecode", help="Load and execute saved bytecode")
    run_bc_parser.add_argument("input", type=Path, help="Input bytecode file", nargs="+")

    subparsers.add_parser("tests", help="Run tests")

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

    if args.command == "tests":
        from tests.test_file_outputs import run_tests
        run_tests(compiler=compile_program, parser=parse_code, vm=VirtualMachine)
        return

    raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
