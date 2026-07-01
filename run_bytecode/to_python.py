from types import NoneType
from typing import cast

from ast_to_bytecode.instructions import Bytecode, FunctionInfo, Instruction


class VarNames:
    def __init__(self):
        for attr in VarNames.__dict__:
            if not attr.startswith("__"):
                self.__dict__[attr] = VarNames.__dict__[attr]

    STACK: str = "STACK"
    ANY: str = "Any"
    VAL: str = "val"
    VALUE: str = "value"
    ADD: str = "add"
    GET_INDEX: str = "get_index"
    SET_INDEX: str = "set_index"
    PRINT: str = "print"
    LEN: str = "len"
    IS_INSTANCE: str = "isinstance"
    IP: str = "ip"
    COPY: str = "copy"


class Goto(BaseException):
    def __init__(self, line: int, condition: str | None = None):
        self.line = line
        self.condition = condition


add_functions: set[str] = set()


def is_in(var_name: str, bytecode: Bytecode | FunctionInfo) -> bool:
    if isinstance(bytecode, Bytecode):
        if var_name in bytecode.functions:
            return True
        for func_info in bytecode.functions.values():
            if is_in(var_name, func_info):
                return True
    for instr in bytecode.instructions:
        if instr.arg == var_name:
            return True
    return False


def compile_instruction_to_python(instr: Instruction, var_names: VarNames, *, is_in_funct: bool = False) -> list[str]:
    match instr.op:
        case "HALT":
            return ["return" if is_in_funct else "exit()"]

        case "PUSH":
            if isinstance(instr.arg, (int, float, bool, NoneType)):
                return [f"{var_names.STACK}.append({instr.arg})"]
            return [
                f"{var_names.STACK}.append(\"{str(instr.arg).replace('\"', '\\\"')}\")",
            ]

        case "LOAD":
            return [f"{var_names.STACK}.append({var_names.COPY}.deepcopy({instr.arg}))"]

        case "STORE":
            return [f"{instr.arg}: {var_names.ANY} = {var_names.STACK}.pop()"]

        case "POP":
            return [f"{var_names.STACK}.pop()"]

        case "PRINT":
            add_functions.add("print")
            return [
                f"{var_names.PRINT}({var_names.STACK}.pop())",
            ]

        case "NEG":
            return [f"{var_names.STACK}.append(-{var_names.STACK}.pop())"]

        case "NOT":
            return [f"{var_names.STACK}.append(not {var_names.STACK}.pop())"]

        case "ADD":
            # Add is weird
            # If both are lists:
            #   If both are list of same types of elements, concatenate
            #   If right is a list of strings, convert each element of left to strings and concatenate
            #   Otherwise convert each element of right to the type of left and concatenate
            # If only one is a list, convert the other to the type of the list and add it to the list
            # Otherwise, just add them
            add_functions.add("add")
            return [
                f"{var_names.STACK}.append({var_names.ADD}({var_names.STACK}.pop(-2), {var_names.STACK}.pop()))"
            ]

        case "SUB" | "MUL" | "DIV" | "MOD" | "POW" | "EQ" | "NE" | "LT" | "LE" | "GT" | "GE":
            op = {
                "SUB": "-",
                "MUL": "*",
                "DIV": "/",
                "MOD": "%",
                "POW": "**",
                "EQ": "==",
                "NE": "!=",
                "LT": "<",
                "LE": "<=",
                "GT": ">",
                "GE": ">=",
            }
            return [f"{var_names.STACK}.append({var_names.STACK}.pop(-2) {op[instr.op]} {var_names.STACK}.pop())"]

        case "AND" | "OR" | "XOR":
            op = {
                "AND": "and",
                "OR": "or",
                "XOR": "^",
            }
            return [f"{var_names.STACK}.append(bool({var_names.STACK}.pop(-2)) {op[instr.op]} bool({var_names.STACK}.pop()))"]

        case "MAKE_LIST":
            size = int(instr.arg)
            if size < 0:
                raise ValueError(f"Invalid size for MAKE_LIST: {size}")
            if size == 0:
                return [f"{var_names.STACK}.append([])"]
            return [
                f"{var_names.STACK}.append({var_names.COPY}.deepcopy([{var_names.STACK}.pop() for _ in range({size})][::-1]))"
            ]

        case "GET_INDEX":
            count = int(instr.arg)
            add_functions.add("get_index")
            return [
                f"{var_names.STACK}.append({var_names.GET_INDEX}({count}))",
            ]

        case "SET_INDEX":
            name, count = instr.arg
            add_functions.add("set_index")
            return [
                f"{var_names.SET_INDEX}({name}, {count})",
            ]

        case "CALL":
            func_name, argc = instr.arg["name"], int(instr.arg["argc"])
            return [
                f"{var_names.STACK}.append({var_names.COPY}.deepcopy("
                f"{func_name}(*[{var_names.STACK}.pop() for _ in range({argc})][::-1])))"
            ]

        case "RET":
            return [f"return {var_names.STACK}.pop() if {var_names.STACK} else None"]

        case "TRY":
            error_name = str(instr.arg["error_name"])
            try_instructions = instr.arg["try_instructions"]
            catch_instructions = instr.arg["catch_instructions"]
            try_code = [compile_instruction_to_python(i, var_names, is_in_funct=is_in_funct) for i in try_instructions]
            catch_code = [compile_instruction_to_python(i, var_names, is_in_funct=is_in_funct) for i in catch_instructions]
            try_code = [line for sublist in try_code for line in sublist]
            catch_code = [line for sublist in catch_code for line in sublist]
            try_code = [f"    {line}" for line in try_code]
            catch_code = [f"    {line}" for line in catch_code]
            return [
                "try:",
                *try_code,
                f"except Exception as {error_name}:",
                *catch_code,
            ]

        case "JUMP":
            raise Goto(instr.arg)

        case "JUMP_IF_FALSE":
            raise Goto(instr.arg, condition=f"not {var_names.STACK}.pop()")

        case "MAKE_RANGE":
            return [f"{var_names.STACK}.append(slice({var_names.STACK}.pop(-2), {var_names.STACK}.pop()))"]

        case _:
            raise ValueError(f"Unsupported instruction: {instr.op}")


def compile_function_to_python(func_name: str, func_info: FunctionInfo, var_names: VarNames) -> list[str]:
    lines = [
        f"def {func_name}({', '.join(f'{param}: {var_names.ANY}' for param in func_info.params)}):",
    ]
    code_lines: list[list[str] | Goto] = []
    for ind, instr in enumerate(func_info.instructions):
        try:
            code_lines.append(
                list(f"    {line}" for line in compile_instruction_to_python(instr, var_names, is_in_funct=True))
            )
        except Goto as goto:
            code_lines.append(goto)

    # Remove the push None and ret None at the end of the function
    # Don't need to return None explicitly in python
    code_lines.pop()
    code_lines.pop()

    if not code_lines or not any(line for line in code_lines if line):
        lines.append("    pass")
    if any(isinstance(line, Goto) for line in code_lines):
        ind = -1
        usefull: list[int] = [goto.line for goto in code_lines if isinstance(goto, Goto)]
        usefull.extend([idx for idx, goto in enumerate(code_lines) if isinstance(goto, Goto)])
        usefull = list(set(usefull))
        usefull.sort()
        minimum = min(usefull)
        lines.extend([
            line for lines in cast(list[list[str]], code_lines[:minimum]) for line in lines
        ])
        lines.append(f"    {var_names.IP}: int = {minimum}")
        lines.append("    while True:")
        count = 0
        for ind, line in enumerate(code_lines):
            if ind < minimum:
                continue
            if ind in usefull:
                if ind != minimum and lines[-1].strip() != "continue":
                    lines.append(f"            {var_names.IP} += {count}")
                lines.append(f"        if {var_names.IP} == {ind}:")
                count = 0
            count += 1
            if isinstance(line, Goto):
                if line.condition is not None:
                    lines.append(f"            if {line.condition}:")
                    lines.append(f"                {var_names.IP} = {line.line}")
                    lines.append("                continue")
                else:
                    lines.append(f"            {var_names.IP} = {line.line}")
                    lines.append("            continue")
            else:
                lines.extend([f"        {line}" for line in line])
        lines.append(f"            {var_names.IP} += {count}")
        lines.append(f"        if {var_names.IP} > {ind}:")
        lines.append("            break")
    else:
        lines.extend([line for _lines in cast(list[list[str]], code_lines) for line in _lines])

    return lines


functions_code: dict[str, str] = {
    "get_index": """
def {GET_INDEX}(count: int):
    index_stack = list({STACK}.pop() for _ in range(count))
    {VAL} = {STACK}.pop()
    while index_stack:
        index = index_stack.pop()
        {VAL} = {VAL}[index]
    return {VAL}
""",
    "set_index": """
def {SET_INDEX}({VAL}: {ANY}, count: int):
    {VALUE} = {STACK}.pop()
    index_stack = list({STACK}.pop() for _ in range(count))
    index = index_stack.pop()
    while index_stack:
        {VAL} = {VAL}[index]
        index = index_stack.pop()
    {VAL}[index] = {VALUE}
""",
    "print": """
def {PRINT}(value: {ANY}):
    if {IS_INSTANCE}(value, float) and value.is_integer():
        value = int(value)
    if {IS_INSTANCE}(value, str):
        value = "'" + value + "'"
    if {IS_INSTANCE}(value, list) and all(
        {IS_INSTANCE}(item, str) for item in value  # type: ignore [reportUnknownVariableType]
    ):
        value = "".join(value)
    __builtins__.print(value, end="")
""",
    "add": """
def {ADD}(left: {ANY}, right: {ANY}) -> {ANY}:
    left_is_list = {IS_INSTANCE}(left, list)
    right_is_list = {IS_INSTANCE}(right, list)
    if left_is_list and right_is_list:
        if {LEN}(left) == 0 or {LEN}(right) == 0 or type(left[0]) is type(right[0]):
            return left + right  # type: ignore
        if type(right[0]) is str:
            return [str(left_val) for left_val in left] + right  # type: ignore
        type_left = type(left[0])  # type: ignore
        right = [type_left(right_val) for right_val in right]  # type: ignore
        return left + right

    if left_is_list and not right_is_list:
        t = type(left[0]) if left else None  # type: ignore
        if t is not None and not {IS_INSTANCE}(right, t):
            right = t(right)
        return left + [right]  # type: ignore

    if not left_is_list and right_is_list:
        t = type(right[0]) if right else None  # type: ignore
        if t is not None and not {IS_INSTANCE}(left, t):
            left = t(left)
        return [left] + right

    assert not left_is_list and not right_is_list, "Impossible case due to earlier checks"
    return left + right
"""
}


def python_export(bytecode: Bytecode) -> str:
    """
    Export the given bytecode to a Python file.

    Args:
        bytecode (Bytecode): The bytecode to export.
        output_path (str | Path): The path to the output Python file.
    """
    var_names = VarNames()
    for attr in VarNames.__dict__:
        if not attr.startswith("__"):
            while is_in(getattr(var_names, attr), bytecode):
                setattr(var_names, attr, getattr(var_names, attr) + "_")
    lines = [
        "# Auto-generated Python code from bytecode",
        "# pyright: reportPossiblyUnboundVariable=false",
        "# pyright: reportRedeclaration=false",
        f"from typing import Any as {var_names.ANY}",
        f"import copy as {var_names.COPY}",
        "",
    ]
    if is_in("true", bytecode):
        lines.append("true: bool = True")
    if is_in("false", bytecode):
        lines.append("false: bool = False")
    if is_in("len", bytecode):
        lines.append(f"{var_names.LEN} = len")
    if is_in("is_instance", bytecode):
        lines.append(f"{var_names.IS_INSTANCE} = isinstance")
    lines.extend([
        f"{var_names.STACK}: list[{var_names.ANY}] = []",
        "",
    ])

    func_lines: list[str] = []
    for func_name, func_info in bytecode.functions.items():
        func_lines.append("")
        func_lines.extend(compile_function_to_python(func_name, func_info, var_names))
        func_lines.append("")
    func_lines.append("")

    code_lines: list[list[str] | Goto] = []
    for instr in bytecode.instructions:
        try:
            code_lines.append(compile_instruction_to_python(instr, var_names))
        except Goto as goto:
            code_lines.append(goto)

    for func_name in add_functions:
        if func_name in functions_code:
            lines.append("")
            lines.extend(functions_code[func_name].format(**vars(var_names)).split("\n"))

    lines.extend(func_lines)

    if not code_lines or not any(line for line in code_lines if line):
        lines.append("pass")
    if any(isinstance(line, Goto) for line in code_lines):
        ind = -1
        usefull: list[int] = [goto.line for goto in code_lines if isinstance(goto, Goto)]
        usefull.extend([idx for idx, goto in enumerate(code_lines) if isinstance(goto, Goto)])
        usefull = list(set(usefull))
        usefull.sort()
        minimum = min(usefull)
        lines.extend([
            line for lines in cast(list[list[str]], code_lines[:minimum]) for line in lines
        ])
        lines.append(f"{var_names.IP}: int = {minimum}")
        lines.append("while True:")
        count = 0
        for ind, line in enumerate(code_lines):
            if ind < minimum:
                continue
            if ind in usefull:
                if ind != minimum and lines[-1].strip() != "continue":
                    lines.append(f"        {var_names.IP} += {count}")
                lines.append(f"    if {var_names.IP} == {ind}:")
                count = 0
            count += 1
            if isinstance(line, Goto):
                if line.condition is not None:
                    lines.append(f"        if {line.condition}:")
                    lines.append(f"            {var_names.IP} = {line.line}")
                    lines.append("            continue")
                else:
                    lines.append(f"        {var_names.IP} = {line.line}")
                    lines.append("        continue")
            else:
                lines.extend([f"        {line}" for line in line])
        lines.append(f"        {var_names.IP} += {count}")
        lines.append(f"    if {var_names.IP} > {ind}:")
        lines.append("        break")
    else:
        lines.extend([line for _lines in cast(list[list[str]], code_lines) for line in _lines])

    for i, line in enumerate(lines):
        if line.strip() == "":
            lines[i] = ""
    empty_lines = [i for i, line in enumerate(lines) if line == ""]
    if empty_lines:
        for j in empty_lines:
            if j > 0 and j < len(lines) - 1:
                if lines[j - 1] == "" and lines[j + 1] == "":
                    lines[j] = None  # type: ignore
        lines = [line for line in lines if line is not None]  # type: ignore

    return "\n".join(lines).strip() + "\n"
