from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Instruction:
    op: str
    arg: Any = None


@dataclass
class FunctionInfo:
    params: list[str]
    instructions: list[Instruction]


@dataclass
class Bytecode:
    instructions: list[Instruction]
    functions: dict[str, FunctionInfo]
