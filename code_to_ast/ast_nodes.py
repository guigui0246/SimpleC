from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any


@dataclass(frozen=True)
class Program:
    statements: list[Stmt]


class Stmt:
    pass


class Expr:
    pass


class TypeType(enum.Enum):
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STRING = "string"
    CHAR = "char"
    VOID = "void"


@dataclass(frozen=True)
class Type:
    base: TypeType
    # For arrays, we can have dimensions like [10][20], which would be represented as [10, 20]
    array_dims: list[int] | None = None


@dataclass(frozen=True)
class VarDecl(Stmt):
    name: str
    type: Type
    value: Expr


@dataclass(frozen=True)
class Assign(Stmt):
    name: str
    value: Expr


@dataclass(frozen=True)
class Print(Stmt):
    value: Expr


@dataclass(frozen=True)
class If(Stmt):
    condition: Expr
    then_body: list[Stmt]
    else_body: list[Stmt] | None


@dataclass(frozen=True)
class While(Stmt):
    condition: Expr
    body: list[Stmt]


@dataclass(frozen=True)
class For(Stmt):
    init: Stmt | None
    update: Stmt | None
    condition: Expr | None
    body: list[Stmt]


@dataclass(frozen=True)
class Return(Stmt):
    value: Expr


@dataclass(frozen=True)
class FunctionParam:
    name: str
    type: Type


@dataclass(frozen=True)
class FunctionDef(Stmt):
    name: str
    params: list[FunctionParam]
    return_type: Type
    body: list[Stmt]


@dataclass(frozen=True)
class TryCatch(Stmt):
    try_body: list[Stmt]
    error_name: str
    catch_body: list[Stmt]


@dataclass(frozen=True)
class ExprStmt(Stmt):
    expr: Expr


@dataclass(frozen=True)
class ArrayAssign(Stmt):
    name: str
    index: Expr
    value: Expr


@dataclass(frozen=True)
class Number(Expr):
    value: int


@dataclass(frozen=True)
class FloatNumber(Expr):
    value: float


@dataclass(frozen=True)
class BoolValue(Expr):
    value: bool


@dataclass(frozen=True)
class StringValue(Expr):
    value: str


@dataclass(frozen=True)
class CharValue(Expr):
    value: str


@dataclass(frozen=True)
class Var(Expr):
    name: str


@dataclass(frozen=True)
class BinOp(Expr):
    left: Expr
    op: str
    right: Expr


@dataclass(frozen=True)
class UnaryOp(Expr):
    op: str
    operand: Expr


@dataclass(frozen=True)
class ArrayLiteral(Expr):
    values: list[Expr]


@dataclass(frozen=True)
class IndexAccess(Expr):
    target: Expr
    index: Expr


@dataclass(frozen=True)
class Call(Expr):
    name: str
    args: list[Expr]


@dataclass(frozen=True)
class VoidValue(Expr):
    value: Any = None
