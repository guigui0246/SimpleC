from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ast_to_bytecode.instructions import Bytecode, FunctionInfo, Instruction

try:
    from .to_python import python_export
except ImportError:
    python_export = None  # type: ignore


BYTECODE_VERSION = 1


def json_export(bytecode: Bytecode) -> str:
    def serialize_instruction(instr: Instruction) -> dict[str, Any]:
        return {"op": instr.op, "arg": instr.arg}

    payload: dict[str, Any] = {
        "version": BYTECODE_VERSION,
        "instructions": [serialize_instruction(i) for i in bytecode.instructions],
        "functions": {
            name: {
                "params": info.params,
                "instructions": [serialize_instruction(i) for i in info.instructions],
            }
            for name, info in bytecode.functions.items()
        },
    }
    return json.dumps(payload, indent=2)


def save_bytecode(bytecode: Bytecode, output_path: str | Path, format: str = "json") -> None:
    if format == "json":
        Path(output_path).write_text(json_export(bytecode), encoding="utf-8")
    elif format == "python" and python_export is not None:
        Path(output_path).write_text(python_export(bytecode), encoding="utf-8")
    else:
        raise ValueError(f"Unsupported format: {format}")


def available_bytecode_formats() -> list[str]:
    available = ["json"]
    if python_export is not None:
        available.append("python")
    return available


def load_bytecode(input_path: str | Path) -> Bytecode:
    raw = Path(input_path).read_text(encoding="utf-8")
    payload = json.loads(raw)

    if payload.get("version") != BYTECODE_VERSION:
        raise ValueError(
            f"Unsupported bytecode version: {payload.get('version')}, expected {BYTECODE_VERSION}"
        )

    instructions = [
        Instruction(op=item["op"], arg=item.get("arg")) for item in payload.get("instructions", [])
    ]

    functions: dict[str, FunctionInfo] = {}
    for name, info in payload.get("functions", {}).items():
        fn_instructions = [
            Instruction(op=item["op"], arg=item.get("arg")) for item in info.get("instructions", [])
        ]
        functions[name] = FunctionInfo(params=list(info.get("params", [])), instructions=fn_instructions)

    return Bytecode(instructions=instructions, functions=functions)
