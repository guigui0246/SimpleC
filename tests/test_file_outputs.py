from __future__ import annotations

from pathlib import Path
import sys
from typing import TYPE_CHECKING, Any, Callable, Type, Protocol
import unittest


ROOT_DIR = Path(__file__).resolve().parents[1]
TEST_FILES_DIR = ROOT_DIR / "tests" / "files"
STANDARD_LIB_DIR = ROOT_DIR / "standard_lib"


if TYPE_CHECKING:
    from ..ast_to_bytecode.instructions import Bytecode
    from ..ast_to_bytecode.compiler import compile_program
    from ..code_to_ast.parser import parse_code
    from ..run_bytecode.vm import VirtualMachine
else:
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    from ast_to_bytecode.compiler import compile_program
    from code_to_ast.parser import parse_code
    from run_bytecode.vm import VirtualMachine


class VirtualMachineProto(Protocol):
    def run(self, bytecode: Bytecode) -> str:
        ...


def _normalize_output(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def _load_standard_lib_source() -> str:
    sources = [
        lib_file.read_text(encoding="utf-8")
        for lib_file in sorted(STANDARD_LIB_DIR.glob("*.glados"))
    ]
    return "\n\n".join(sources)


STANDARD_LIB_SOURCE = _load_standard_lib_source()


def _expected_path_for_input(input_path: Path, expected_dir: Path) -> Path:
    stem = input_path.stem
    suffix = input_path.suffix
    candidates: list[Path] = [expected_dir / f"{stem}{suffix}"]

    # Support naming patterns like input1.txt -> expected1.txt
    if stem.startswith("input"):
        case_id = stem[len("input"):]
        candidates.append(expected_dir / f"expected{case_id}{suffix}")
        candidates.append(expected_dir / f"test{case_id}{suffix}")
    elif stem.startswith("test"):
        case_id = stem[len("test"):]
        candidates.append(expected_dir / f"expected{case_id}{suffix}")

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"No expected file found for '{input_path.name}' in '{expected_dir}'"
    )


def _run_program(source_code: str, use_standard_lib: bool = False) -> str:
    program_source = source_code
    if use_standard_lib:
        program_source = f"{STANDARD_LIB_SOURCE}\n\n{source_code}"

    ast = parse_code(program_source)
    bytecode = compile_program(ast)
    vm = VirtualMachine()
    return vm.run(bytecode)


def _isolated_run_python_bytecode(python_code: str) -> str:
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as temp_file:
        temp_file.write(python_code)
        temp_file_path = temp_file.name

    try:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", temp_file_path],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8"
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Python execution failed with exit code {e.returncode}:\n{e.stderr}"
        )
    finally:
        Path(temp_file_path).unlink(missing_ok=True)


class TestInputExpectedOutputs(unittest.TestCase):
    def _run_suite(self, suite_name: str, use_standard_lib: bool = False) -> None:
        input_dir = TEST_FILES_DIR / suite_name / "input"
        expected_dir = TEST_FILES_DIR / suite_name / "expected"

        self.assertTrue(input_dir.exists(), f"Missing input directory: {input_dir}")
        self.assertTrue(expected_dir.exists(), f"Missing expected directory: {expected_dir}")

        input_files = sorted(input_dir.glob("*.txt"))
        self.assertTrue(input_files, f"No input files found in {input_dir}")

        for input_file in input_files:
            expected_file = _expected_path_for_input(input_file, expected_dir)
            source_code = input_file.read_text(encoding="utf-8")
            expected_output = expected_file.read_text(encoding="utf-8")

            with self.subTest(case=f"{suite_name}/{input_file.name}"):
                actual_output = _run_program(
                    source_code=source_code,
                    use_standard_lib=use_standard_lib,
                )
                self.assertEqual(
                    _normalize_output(actual_output),
                    _normalize_output(expected_output),
                    (
                        f"Output mismatch for {suite_name}/{input_file.name}. "
                        f"Expected file: {expected_file.name}"
                    ),
                )

    def test_simple_suite(self) -> None:
        self._run_suite("simple", use_standard_lib=False)

    def test_hard_suite(self) -> None:
        self._run_suite("hard", use_standard_lib=False)

    def test_standard_lib_suite(self) -> None:
        self._run_suite("standard_lib", use_standard_lib=True)


class TestPythonCompilerOutputs(unittest.TestCase):
    def _run_suite(self, suite_name: str, use_standard_lib: bool = False) -> None:
        from run_bytecode.to_python import python_export
        input_dir = TEST_FILES_DIR / suite_name / "input"
        expected_dir = TEST_FILES_DIR / suite_name / "expected"

        self.assertTrue(input_dir.exists(), f"Missing input directory: {input_dir}")
        self.assertTrue(expected_dir.exists(), f"Missing expected directory: {expected_dir}")

        input_files = sorted(input_dir.glob("*.txt"))
        self.assertTrue(input_files, f"No input files found in {input_dir}")

        for input_file in input_files:
            expected_file = _expected_path_for_input(input_file, expected_dir)
            source_code = input_file.read_text(encoding="utf-8")
            expected_output = expected_file.read_text(encoding="utf-8")

            with self.subTest(case=f"{suite_name}/{input_file.name}"):
                program_source = source_code
                if use_standard_lib:
                    program_source = f"{STANDARD_LIB_SOURCE}\n\n{source_code}"

                ast = parse_code(program_source)
                bytecode = compile_program(ast)
                python_code = python_export(bytecode)
                actual_output = _isolated_run_python_bytecode(python_code)
                self.assertEqual(
                    _normalize_output(actual_output),
                    _normalize_output(expected_output),
                    (
                        f"Output mismatch for {suite_name}/{input_file.name}. "
                        f"Expected file: {expected_file.name}"
                    ),
                )

    def test_simple_suite(self) -> None:
        self._run_suite("simple", use_standard_lib=False)

    def test_hard_suite(self) -> None:
        self._run_suite("hard", use_standard_lib=False)

    def test_standard_lib_suite(self) -> None:
        self._run_suite("standard_lib", use_standard_lib=True)


if __name__ == "__main__":
    unittest.main()
else:
    def run_tests(compiler: Callable[[Any], Any], parser: Callable[[Any], Any], vm: Type[VirtualMachineProto]) -> None:
        global compile_program, parse_code, VirtualMachine
        compile_program = compiler
        parse_code = parser
        VirtualMachine = vm
        suite = unittest.TestLoader().loadTestsFromTestCase(TestInputExpectedOutputs)
        unittest.TextTestRunner(verbosity=2).run(suite)
        suite = unittest.TestLoader().loadTestsFromTestCase(TestPythonCompilerOutputs)
        unittest.TextTestRunner(verbosity=2).run(suite)
