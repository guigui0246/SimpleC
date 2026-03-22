from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Program:
    statements: list[Stmt]


class Stmt:
    pass


class Expr:
    pass


@dataclass(frozen=True)
class VarDecl(Stmt):
    name: str
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
class FunctionDef(Stmt):
    name: str
    params: list[str]
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
