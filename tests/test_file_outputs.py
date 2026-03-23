from __future__ import annotations

from pathlib import Path
import unittest

from ast_to_bytecode import compile_program
from code_to_ast import parse_code
from run_bytecode import VirtualMachine


ROOT_DIR = Path(__file__).resolve().parents[1]
TEST_FILES_DIR = ROOT_DIR / "tests" / "files"
STANDARD_LIB_DIR = ROOT_DIR / "standard_lib"


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


if __name__ == "__main__":
    unittest.main()
