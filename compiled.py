# Auto-generated Python code from bytecode
# pyright: reportPossiblyUnboundVariable=false
# pyright: reportRedeclaration=false
from typing import Any as Any
import copy

STACK: list[Any] = []


def print(value: Any):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, str):
        value = "'" + value + "'"
    if isinstance(value, list) and all(
        isinstance(item, str) for item in value  # type: ignore [reportUnknownVariableType]
    ):
        value = "".join(value)
    __builtins__.print(value, end="")


def add(left: Any, right: Any) -> Any:
    left_is_list = isinstance(left, list)
    right_is_list = isinstance(right, list)
    if left_is_list and right_is_list:
        if len(left) == 0 or len(right) == 0 or type(left[0]) is type(right[0]):
            return left + right  # type: ignore
        if type(right[0]) is str:
            return [str(left_val) for left_val in left] + right  # type: ignore
        type_left = type(left[0])  # type: ignore
        right = [type_left(right_val) for right_val in right]  # type: ignore
        return left + right

    if left_is_list and not right_is_list:
        t = type(left[0]) if left else None  # type: ignore
        if t is not None and not isinstance(right, t):
            right = t(right)
        return left + [right]  # type: ignore

    if not left_is_list and right_is_list:
        t = type(right[0]) if right else None  # type: ignore
        if t is not None and not isinstance(left, t):
            left = t(left)
        return [left] + right

    assert not left_is_list and not right_is_list, "Impossible case due to earlier checks"
    return left + right


STACK.append(10)
a: Any = STACK.pop()
STACK.append(copy.deepcopy(a))
STACK.append(5)
STACK.append(STACK.pop(-2) < STACK.pop())
ip: int = 5
while True:
    if ip == 5:
        if not STACK.pop():
            ip = 16
            continue
        STACK.append("i")
        STACK.append("f")
        STACK.append(" ")
        STACK.append(copy.deepcopy([STACK.pop() for _ in range(3)][::-1]))
        print(STACK.pop())
        STACK.append(copy.deepcopy(a))
        STACK.append(1)
        STACK.append(add(STACK.pop(-2), STACK.pop()))
        a: Any = STACK.pop()
        ip += 10
    if ip == 15:
        ip = 54
        continue
    if ip == 16:
        STACK.append(copy.deepcopy(a))
        STACK.append(10)
        STACK.append(STACK.pop(-2) == STACK.pop())
        ip += 3
    if ip == 19:
        if not STACK.pop():
            ip = 43
            continue
        STACK.append("e")
        STACK.append("l")
        STACK.append("i")
        STACK.append("f")
        STACK.append(" ")
        STACK.append(copy.deepcopy([STACK.pop() for _ in range(5)][::-1]))
        print(STACK.pop())
        STACK.append(copy.deepcopy(a))
        STACK.append(2)
        STACK.append(STACK.pop(-2) % STACK.pop())
        STACK.append(0)
        STACK.append(STACK.pop(-2) == STACK.pop())
        ip += 13
    if ip == 32:
        if not STACK.pop():
            ip = 38
            continue
        STACK.append(copy.deepcopy(a))
        STACK.append(2)
        STACK.append(STACK.pop(-2) * STACK.pop())
        a: Any = STACK.pop()
        ip += 5
    if ip == 37:
        ip = 42
        continue
    if ip == 38:
        STACK.append(copy.deepcopy(a))
        STACK.append(2)
        STACK.append(STACK.pop(-2) ** STACK.pop())
        a: Any = STACK.pop()
        ip += 4
    if ip == 42:
        ip = 54
        continue
    if ip == 43:
        STACK.append("e")
        STACK.append("l")
        STACK.append("s")
        STACK.append("e")
        STACK.append(" ")
        STACK.append(copy.deepcopy([STACK.pop() for _ in range(5)][::-1]))
        print(STACK.pop())
        STACK.append(copy.deepcopy(a))
        STACK.append(3)
        STACK.append(STACK.pop(-2) - STACK.pop())
        a: Any = STACK.pop()
        ip += 11
    if ip == 54:
        STACK.append(copy.deepcopy(a))
        print(STACK.pop())
        ip += 2
    if ip > 55:
        break
