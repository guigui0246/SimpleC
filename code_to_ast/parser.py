from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from lark import Lark, Token, Transformer

from .ast_nodes import (
    ArrayAssign,
    ArrayLiteral,
    Assign,
    BinOp,
    BoolValue,
    Call,
    Expr,
    ExprStmt,
    FloatNumber,
    For,
    FunctionDef,
    If,
    IndexAccess,
    Number,
    Print,
    Program,
    Return,
    Stmt,
    StringValue,
    TryCatch,
    UnaryOp,
    Var,
    VarDecl,
    VoidValue,
    While,
)


class ToAst(Transformer[Any, Any]):
    def start(self, items: list[Any]) -> Program:
        (program,) = items
        if not isinstance(program, Program):
            raise TypeError(f"Expected Program, got: {type(program).__name__}")
        return program

    def program(self, items: list[Any]) -> Program:
        statements: list[Stmt] = [item for item in items if isinstance(item, Stmt)]
        return Program(statements=statements)

    def block(self, items: list[Any]) -> list[Stmt]:
        return [item for item in items if isinstance(item, Stmt)]

    def var_decl(self, items: list[Any]) -> VarDecl:
        name_token, expr = items
        return VarDecl(name=str(name_token), value=expr)

    def assign(self, items: list[Any]) -> Assign:
        name_token, expr = items
        return Assign(name=str(name_token), value=expr)

    def array_assign(self, items: list[Any]) -> ArrayAssign:
        name_token, index, expr = items
        return ArrayAssign(name=str(name_token), index=index, value=expr)

    def print_stmt(self, items: list[Any]) -> Print:
        (expr,) = items
        return Print(value=expr)

    def if_stmt(self, items: list[Any]) -> If:
        condition = items[0]
        then_body = items[1]
        elif_branches: list[tuple[Expr, list[Stmt]]] = []
        else_body: list[Stmt] | None = None

        for chunk in items[2:]:
            if isinstance(chunk, tuple):
                elif_branches.append(chunk)
            elif isinstance(chunk, list):
                else_body = self._as_stmt_list(chunk)

        node = If(condition=condition, then_body=then_body, else_body=else_body)
        for elif_condition, elif_body in reversed(elif_branches):
            node = If(condition=elif_condition, then_body=elif_body, else_body=[node])
        return node

    def elif_clause(self, items: list[Any]) -> tuple[Expr, list[Stmt]]:
        condition, body = items
        return (condition, body)

    def else_clause(self, items: list[Any]) -> list[Stmt]:
        (body,) = items
        return body

    def while_stmt(self, items: list[Any]) -> While:
        condition, body = items
        return While(condition=condition, body=body)

    def for_var_decl(self, items: list[Any]) -> VarDecl:
        name_token, expr = items
        return VarDecl(name=str(name_token), value=expr)

    def for_assign(self, items: list[Any]) -> Assign:
        name_token, expr = items
        return Assign(name=str(name_token), value=expr)

    def for_stmt(self, items: list[Any]) -> For:
        body = items[-1]
        fragments = items[:-1]

        init: Stmt | None = None
        condition: Expr | None = None
        update: Stmt | None = None

        for fragment in fragments:
            if isinstance(fragment, Stmt):
                if init is None:
                    init = fragment
                else:
                    update = fragment
            else:
                condition = fragment

        return For(init=init, condition=condition, update=update, body=body)

    def params(self, items: list[Any]) -> list[str]:
        return [str(item) for item in items]

    def fun_def(self, items: list[Any]) -> FunctionDef:
        name_token = items[0]
        params: list[str] = []
        body: list[Stmt] = []

        if len(items) == 2:
            body = items[1]
        elif len(items) == 3:
            params = items[1]
            body = items[2]

        return FunctionDef(name=str(name_token), params=params, body=body)

    def return_stmt(self, items: list[Any]) -> Return:
        (value,) = items
        return Return(value=value)

    def try_catch_stmt(self, items: list[Any]) -> TryCatch:
        try_body, err_name, catch_body = items
        return TryCatch(try_body=try_body, error_name=str(err_name), catch_body=catch_body)

    def expr_stmt(self, items: list[Any]) -> ExprStmt:
        (expr,) = items
        return ExprStmt(expr=expr)

    def number(self, items: list[Any]) -> Number:
        (token,) = items
        return Number(value=int(token))

    def float_number(self, items: list[Any]) -> FloatNumber:
        (token,) = items
        return FloatNumber(value=float(token))

    def bool_value(self, items: list[Any]) -> BoolValue:
        (token,) = items
        token_str = str(token).lower()
        return BoolValue(value=(token_str == "true"))

    def string_value(self, items: list[Any]) -> StringValue:
        (token,) = items
        return StringValue(value=ast.literal_eval(str(token)))

    def void_value(self, _items: list[Any]) -> VoidValue:
        return VoidValue()

    def var(self, items: list[Any]) -> Var:
        (token,) = items
        return Var(name=str(token))

    def unary_op(self, items: list[Any]) -> UnaryOp:
        op_token, operand = items
        return UnaryOp(op=str(op_token), operand=operand)

    def call(self, items: list[Any]) -> Call:
        name_token = items[0]
        args: list[Expr] = []
        if len(items) > 1:
            args = items[1]
        return Call(name=str(name_token), args=args)

    def args(self, items: list[Any]) -> list[Expr]:
        return list(items)

    def array_literal(self, items: list[Any]) -> ArrayLiteral:
        return ArrayLiteral(values=list(items))

    def index_access(self, items: list[Any]) -> IndexAccess:
        target, index = items
        return IndexAccess(target=target, index=index)

    def logical_or(self, items: list[Any]) -> Expr:
        return self._fold_binary(items)

    def logical_xor(self, items: list[Any]) -> Expr:
        return self._fold_binary(items)

    def logical_and(self, items: list[Any]) -> Expr:
        return self._fold_binary(items)

    def equality(self, items: list[Any]) -> Expr:
        return self._fold_binary(items)

    def comparison(self, items: list[Any]) -> Expr:
        return self._fold_binary(items)

    def term(self, items: list[Any]) -> Expr:
        return self._fold_binary(items)

    def factor(self, items: list[Any]) -> Expr:
        return self._fold_binary(items)

    def power(self, items: list[Any]) -> Expr:
        return self._fold_binary(items)

    @staticmethod
    def _fold_binary(items: list[Any]) -> Expr:
        if len(items) == 1:
            return items[0]
        expr = items[0]
        i = 1
        while i < len(items):
            op = items[i]
            right = items[i + 1]
            if not isinstance(op, Token):
                raise ValueError(f"Expected operator token, got: {op!r}")
            expr = BinOp(left=expr, op=str(op), right=right)
            i += 2
        return expr

    @staticmethod
    def _as_stmt_list(values: list[Any]) -> list[Stmt]:
        statements: list[Stmt] = []
        for value in values:
            if isinstance(value, Stmt):
                statements.append(value)
        return statements


def _load_grammar() -> str:
    grammar_path = Path(__file__).with_name("grammar.lark")
    return grammar_path.read_text(encoding="utf-8")


_PARSER = Lark(_load_grammar(), parser="lalr", start="start")


def parse_code(source: str) -> Program:
    tree = _PARSER.parse(source)
    transformed: Any = ToAst().transform(tree)
    if not isinstance(transformed, Program):
        raise TypeError(f"Expected Program AST, got: {type(transformed).__name__}")
    return transformed


def parse_file(path: str | Path) -> Program:
    source = Path(path).read_text(encoding="utf-8")
    return parse_code(source)
