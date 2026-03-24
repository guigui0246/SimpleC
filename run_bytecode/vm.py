from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from ast_to_bytecode.instructions import Bytecode, FunctionInfo, Instruction
from code_to_ast.ast_nodes import RangeValue


class VmRuntimeError(Exception):
    pass


@dataclass
class ReturnSignal:
    value: Any


class VirtualMachine:
    def __init__(self) -> None:
        self.stack: list[Any] = []
        self.variables: dict[str, Any] = {
            "true": True,
            "false": False,
        }
        self.output: str = ""
        self.functions: dict[str, FunctionInfo] = {}
        self.index_stack: list[Any] = []

    def run(self, bytecode: Bytecode) -> str:
        self.functions = bytecode.functions
        self._execute_instructions(bytecode.instructions, local_vars=None)
        return self.output

    def _execute_instructions(
        self, instructions: list[Instruction], local_vars: dict[str, Any] | None
    ) -> ReturnSignal | None:
        ip = 0

        while ip < len(instructions):
            instr = instructions[ip]
            op = instr.op
            arg = instr.arg

            if op == "HALT":
                break

            if op == "PUSH":
                self.stack.append(arg)
                ip += 1
                continue

            if op == "LOAD":
                name = str(arg)
                if local_vars is not None and name in local_vars:
                    self.stack.append(local_vars[name])
                elif name in self.variables:
                    self.stack.append(self.variables[name])
                else:
                    raise VmRuntimeError(f"Undefined variable: {name}")
                ip += 1
                continue

            if op == "STORE":
                name = str(arg)
                value = self.stack.pop()
                if local_vars is not None:
                    local_vars[name] = value
                else:
                    self.variables[name] = value
                ip += 1
                continue

            if op == "POP":
                if self.stack:
                    self.stack.pop()
                ip += 1
                continue

            if op == "PRINT":
                value: Any = self.stack.pop()
                if isinstance(value, float) and value.is_integer():
                    value = int(value)
                if isinstance(value, str):
                    value = "'" + value + "'"
                if isinstance(value, list) and all(
                    isinstance(item, str) for item in value  # type: ignore [reportUnknownVariableType]
                ):
                    value = "".join(value)
                self.output += str(value)
                ip += 1
                continue

            if op == "NEG":
                self.stack.append(-self.stack.pop())
                ip += 1
                continue

            if op == "NOT":
                value = self.stack.pop()
                self.stack.append(False if self._truthy(value) else True)
                ip += 1
                continue

            if op in {
                "ADD",
                "SUB",
                "MUL",
                "DIV",
                "MOD",
                "POW",
                "EQ",
                "NE",
                "LT",
                "LE",
                "GT",
                "GE",
                "AND",
                "OR",
                "XOR",
            }:
                right = self.stack.pop()
                left = self.stack.pop()
                self.stack.append(self._binary_op(op, left, right))
                ip += 1
                continue

            if op == "MAKE_LIST":
                count = int(arg)
                if count < 0:
                    raise VmRuntimeError("Negative list size")
                items = self.stack[-count:] if count > 0 else []
                if count > 0:
                    del self.stack[-count:]
                self.stack.append(items)
                ip += 1
                continue

            if op == "GET_INDEX":
                count = int(arg)
                self.index_stack.append(self.stack.pop() for _ in range(count))
                val = self.stack.pop()
                while self.index_stack:
                    index = self.index_stack.pop()
                    try:
                        val = val[index]
                    except (IndexError, KeyError, TypeError) as exc:
                        raise VmRuntimeError(f"Indexing error: {exc}") from exc
                self.stack.append(val)
                ip += 1
                continue

            if op == "SET_INDEX":
                name, count = arg
                self.index_stack.append(self.stack.pop() for _ in range(int(count)))
                value = self.stack.pop()
                val = value
                index = self.index_stack.pop()
                while self.index_stack:
                    val = value[index]
                    index = self.index_stack.pop()
                val[index] = value
                ip += 1
                continue

            if op == "CALL":
                fn_name = str(arg["name"])
                argc = int(arg["argc"])
                args = [self.stack.pop() for _ in range(argc)][::-1]
                self.stack.append(self._call_function(fn_name, args))
                ip += 1
                continue

            if op == "RET":
                value = self.stack.pop() if self.stack else None
                return ReturnSignal(value=value)

            if op == "TRY":
                error_name = str(arg["error_name"])
                try_instructions = arg["try_instructions"]
                catch_instructions = arg["catch_instructions"]

                try_code = [self._to_instruction(i) for i in try_instructions]
                catch_code = [self._to_instruction(i) for i in catch_instructions]

                try:
                    signal = self._execute_instructions(try_code, local_vars=local_vars)
                    self.stack.append(signal.value if signal is not None else None)
                except VmRuntimeError as exc:
                    if local_vars is not None:
                        local_vars[error_name] = str(exc)
                    else:
                        self.variables[error_name] = str(exc)
                    signal = self._execute_instructions(catch_code, local_vars=local_vars)
                    self.stack.append(signal.value if signal is not None else None)

                ip += 1
                continue

            if op == "JUMP":
                ip = int(arg)
                continue

            if op == "JUMP_IF_FALSE":
                value = self.stack.pop()
                if not self._truthy(value):
                    ip = int(arg)
                else:
                    ip += 1
                continue

            if op == "MAKE_RANGE":
                end = self.stack.pop()
                start = self.stack.pop()
                if not (isinstance(start, int | None) and isinstance(end, int | None)):
                    raise VmRuntimeError("Range bounds must be integers")
                self.stack.append(RangeValue(start=start, end=end))
                ip += 1
                continue

            raise ValueError(f"Unknown opcode: {op}")

        return None

    def _call_function(self, name: str, args: list[Any]) -> Any:
        if name == "print":
            for item in args:
                if isinstance(item, float) and item.is_integer():
                    item = int(item)
                if isinstance(item, str):
                    item = "'" + item + "'"
                if isinstance(item, list) and all(isinstance(i, str) for i in item):
                    item = "".join(item)
                self.output += str(item)
            return None

        info = self.functions.get(name)
        if info is None:
            raise VmRuntimeError(f"Undefined function: {name}")
        if len(args) != len(info.params):
            raise VmRuntimeError(
                f"Wrong number of arguments for {name}: expected {len(info.params)}, got {len(args)}"
            )

        local_vars = dict(zip(info.params, args, strict=True))
        signal = self._execute_instructions(info.instructions, local_vars=local_vars)
        return signal.value if signal is not None else None

    @staticmethod
    def _to_instruction(item: dict[str, Any]) -> Instruction:
        return Instruction(op=str(item["op"]), arg=item.get("arg"))

    @staticmethod
    def _truthy(value: Any) -> bool:
        return bool(value)

    @staticmethod
    def _binary_op(op: str, left: Any, right: Any) -> Any:
        if op == "ADD":
            left_is_list = isinstance(left, list)
            right_is_list = isinstance(right, list)
            if left_is_list and right_is_list:
                if len(left) == 0 or len(right) == 0 or type(left[0]) is type(right[0]):
                    return cast(list[Any], left) + cast(list[Any], right)
                if type(right[0]) is str:
                    return [str(left_val) for left_val in cast(list[Any], left)] + cast(list[str], right)
                type_left = cast(type[Any], type(left[0]))
                right = [type_left(right_val) for right_val in cast(list[Any], right)]
                return cast(list[Any], left) + cast(list[Any], right)

            if left_is_list and not right_is_list:
                t = cast(type[Any], type(left[0])) if left else None
                if t is not None and not isinstance(right, t):
                    right = t(right)
                return cast(list[Any], left) + [right]

            if not left_is_list and right_is_list:
                t = cast(type[Any], type(right[0])) if right else None
                if t is not None and not isinstance(left, t):
                    left = t(left)
                return [left] + cast(list[Any], right)

            assert not left_is_list and not right_is_list, "Impossible case due to earlier checks"
            return left + right

        if op == "SUB":
            return left - right
        if op == "MUL":
            return left * right
        if op == "DIV":
            if right == 0:
                raise VmRuntimeError("Division by zero")
            return left / right
        if op == "MOD":
            if right == 0:
                raise VmRuntimeError("Modulo by zero")
            return left % right
        if op == "POW":
            return left**right
        if op == "EQ":
            return left == right
        if op == "NE":
            return left != right
        if op == "LT":
            return left < right
        if op == "LE":
            return left <= right
        if op == "GT":
            return left > right
        if op == "GE":
            return left >= right
        if op == "AND":
            return bool(left) and bool(right)
        if op == "OR":
            return bool(left) or bool(right)
        if op == "XOR":
            return bool(left) ^ bool(right)
        raise ValueError(f"Unknown binary opcode: {op}")
