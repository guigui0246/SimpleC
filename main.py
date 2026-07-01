from __future__ import annotations

import argparse
from pathlib import Path
from ast_to_bytecode import compile_program, Bytecode
from code_to_ast import parse_file, parse_code
from run_bytecode import VirtualMachine, load_bytecode, save_bytecode
from run_bytecode.bytecode_file import available_bytecode_formats


def cmd_parse(source: list[Path]) -> None:
    for src in source:
        ast = parse_file(src)
        print(ast)


def cmd_compile(source: list[Path], output: Path, force: bool, format: str) -> None:
    if not force and output.exists():
        raise ValueError(f"Output file already exists: {output}")

    bytecode: Bytecode = Bytecode([], {})
    for src in source:
        ast = parse_file(src)
        new_code = compile_program(ast)
        bytecode.functions.update(new_code.functions)
        bytecode.instructions.extend(new_code.instructions)
    save_bytecode(bytecode, output, format)
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
    parse_parser.add_argument("source", type=Path, help="Source .sc file", nargs="+")

    compile_parser = subparsers.add_parser("compile", help="Compile source file to bytecode")
    compile_parser.add_argument("source", type=Path, help="Source .sc file", nargs="+")
    compile_parser.add_argument("-o", "--output", type=Path, required=True, help="Output bytecode file")
    compile_parser.add_argument("-f", "--force", action="store_true", help="Overwrite output file if it exists")
    compile_parser.add_argument(
        "--output-format",
        choices=available_bytecode_formats(),
        default="json",
        help="Output format for bytecode (default: json)"
    )

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
        cmd_compile(args.source, args.output, args.force, args.output_format)
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
