from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from lark import Lark, Token, Transformer

from .ast_nodes import (
    ArrayLiteral,
    Assign,
    BinOp,
    BoolValue,
    Call,
    CharValue,
    Expr,
    ExprStmt,
    FloatNumber,
    For,
    FunctionDef,
    FunctionParam,
    If,
    IndexAccess,
    LValue,
    Number,
    Print,
    Program,
    Return,
    Stmt,
    StringValue,
    TryCatch,
    Type,
    TypeType,
    UnaryOp,
    Var,
    VarDecl,
    VoidValue,
    While,
)


def infer_type_from_expr(expr: Expr) -> Type:
    print(f"Infer type from expression: {expr!r}")
    if isinstance(expr, Number):
        return Type(base=TypeType.INT, array_dims=None)
    if isinstance(expr, FloatNumber):
        return Type(base=TypeType.FLOAT, array_dims=None)
    if isinstance(expr, BoolValue):
        return Type(base=TypeType.BOOL, array_dims=None)
    if isinstance(expr, StringValue):
        return Type(base=TypeType.STRING, array_dims=None)
    if isinstance(expr, CharValue):
        return Type(base=TypeType.CHAR, array_dims=None)
    if isinstance(expr, VoidValue):
        return Type(base=TypeType.VOID, array_dims=None)
    if isinstance(expr, ArrayLiteral):
        if not expr.values:
            raise ValueError("Cannot infer type from empty array literal")
        elem_types: list[Type] = [infer_type_from_expr(val) for val in expr.values]
        if not all(elem_type == elem_types[0] for elem_type in elem_types):
            raise ValueError("All elements in array literal must have the same type")
        return Type(base=elem_types[0].base, array_dims=[len(expr.values)] + (elem_types[0].array_dims or []))

    raise ValueError(f"Cannot infer type from expression: {expr!r}")


class ToAst(Transformer[Any, Any]):
    def start(self, items: list[Any]) -> Program:
        (program,) = items
        if not isinstance(program, Program):
            raise TypeError(f"Expected Program, got: {type(program).__name__}")
        return program

    def program(self, items: list[Any]) -> Program:
        statements: list[Stmt] = [item for item in items if isinstance(item, Stmt)]
        return Program(statements=statements)

    def unwrap_statement(self, items: list[Any]) -> Stmt:
        return items[0]

    def drop(self, items: list[Any]) -> None:
        return None

    def block(self, items: list[Any]) -> list[Stmt]:
        return [item for item in items if isinstance(item, Stmt)]

    def var_decl(self, items: list[Any]) -> VarDecl:
        if len(items) == 3:
            type, name_token, expr = items
        else:
            name_token, expr = items
            type = infer_type_from_expr(expr)
        return VarDecl(name=str(name_token), type=type, value=expr)

    def unwrap_any(self, items: list[Any]) -> Any:
        return items[0]

    def lvalue(self, items: list[Any]) -> LValue:
        name_token = items[0]
        if len(items) == 1:
            return LValue(name=str(name_token), indexs=None)
        return LValue(name=str(name_token), indexs=items[1:])

    def assign(self, items: list[Any]) -> Assign:
        name_token, expr = items
        return Assign(name=name_token, value=expr)

    def print_stmt(self, items: list[Any]) -> Print:
        (expr,) = items
        return Print(value=expr)

    def if_stmt(self, items: list[Any]) -> If:
        condition = items[0]
        then_body = items[1]
        elif_branches: list[tuple[Expr, list[Stmt]]] = []
        else_body: list[Stmt] | None = None

        for i in range(2, len(items) - 1, 2):
            elif_branches.append((items[i], items[i + 1]))

        if len(items) % 2 == 1:
            else_body = items[-1]

        if elif_branches:
            current_else_body: list[Stmt] | None = else_body
            for elif_condition, elif_then_body in reversed(elif_branches):
                current_else_body = [If(condition=elif_condition, then_body=elif_then_body, else_body=current_else_body)]
            else_body = current_else_body
        return If(condition=condition, then_body=then_body, else_body=else_body)

    def elif_clause(self, items: list[Any]) -> tuple[Expr, list[Stmt]]:
        condition, body = items
        return (condition, body)

    def else_clause(self, items: list[Any]) -> list[Stmt]:
        (body,) = items
        return body

    def while_stmt(self, items: list[Any]) -> While:
        condition, body = items
        return While(condition=condition, body=body)

    def for_stmt(self, items: list[Any]) -> For:
        init, update, condition, body = items
        return For(init=init, update=update, condition=condition, body=body)

    def TYPE_INT(self, items: list[Any]) -> TypeType:
        return TypeType.INT

    def TYPE_FLOAT(self, items: list[Any]) -> TypeType:
        return TypeType.FLOAT

    def TYPE_BOOL(self, items: list[Any]) -> TypeType:
        return TypeType.BOOL

    def TYPE_STRING(self, items: list[Any]) -> TypeType:
        return TypeType.STRING

    def TYPE_CHAR(self, items: list[Any]) -> TypeType:
        return TypeType.CHAR

    def TYPE_VOID(self, items: list[Any]) -> TypeType:
        return TypeType.VOID

    def unwrap_type(self, items: list[Any]) -> TypeType:
        return items[0]

    def type_parse(self, items: list[Any]) -> Type:
        base_type_token = items[0]
        array_dims: list[int] = []
        for item in items[1:]:
            if isinstance(item, Token) and item.type == "NUMBER":
                array_dims.append(int(item))
        return Type(base=base_type_token, array_dims=array_dims or None)

    def fun_def(self, items: list[Any]) -> FunctionDef:
        name_token = items[0]
        params: list[FunctionParam] = []
        return_type: Type = items[2] if len(items) == 4 else items[1]
        body: list[Stmt] = []

        if len(items) == 3:
            body = items[2]
        elif len(items) == 4:
            params = items[1]
            body = items[3]

        return FunctionDef(name=str(name_token), params=params, return_type=return_type, body=body)

    def params(self, items: list[Any]) -> list[FunctionParam]:
        params: list[FunctionParam] = []
        assert len(items) % 2 == 0, "Expected even number of items in params"
        for i in range(0, len(items), 2):
            type_item = items[i]
            name_item = items[i + 1]
            if not isinstance(type_item, Type):
                raise TypeError(f"Expected Type for parameter, got: {type(type_item).__name__}")
            if not isinstance(name_item, Token):
                raise TypeError(f"Expected Token for parameter name, got: {type(name_item).__name__}")
            params.append(FunctionParam(name=str(name_item), type=type_item))
        return params

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

    def char_value(self, items: list[Any]) -> CharValue:
        (char,) = items
        value = ast.literal_eval(str(char))
        assert isinstance(value, str) and len(value) == 1, "Expected single-character literal"
        return CharValue(value=value)

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
    # print(tree.pretty())
    transformed: Any = ToAst().transform(tree)
    if not isinstance(transformed, Program):
        raise TypeError(f"Expected Program AST, got: {type(transformed).__name__}")
    return transformed


def parse_file(path: str | Path) -> Program:
    source = Path(path).read_text(encoding="utf-8")
    return parse_code(source)
