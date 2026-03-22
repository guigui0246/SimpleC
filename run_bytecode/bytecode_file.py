from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ast_to_bytecode.instructions import Bytecode, FunctionInfo, Instruction


BYTECODE_VERSION = 1


def save_bytecode(bytecode: Bytecode, output_path: str | Path) -> None:
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
    Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


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
