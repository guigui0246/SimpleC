from __future__ import annotations

from typing import Any

from code_to_ast.ast_nodes import (
    ArrayLiteral,
    Assign,
    BinOp,
    BoolValue,
    CharValue,
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
    RangeExpr,
    RangeValue,
    Return,
    Stmt,
    TryCatch,
    UnaryOp,
    Var,
    VarDecl,
    VoidValue,
    While,
)

from .instructions import Bytecode, FunctionInfo, Instruction


class Compiler:
    def __init__(self) -> None:
        self.instructions: list[Instruction] = []
        self.functions: dict[str, FunctionInfo] = {}

    def emit(self, op: str, arg: Any = None) -> int:
        index = len(self.instructions)
        self.instructions.append(Instruction(op=op, arg=arg))
        return index

    def patch(self, index: int, arg: int) -> None:
        self.instructions[index].arg = arg

    def current(self) -> int:
        return len(self.instructions)

    def compile_program(self, program: Program) -> Bytecode:
        for stmt in program.statements:
            self.compile_stmt(stmt)
        return Bytecode(instructions=self.instructions, functions=self.functions)

    def compile_stmt(self, stmt: Stmt) -> None:
        if isinstance(stmt, VarDecl):
            self.compile_expr(stmt.value)
            self.emit("STORE", stmt.name)
            return

        if isinstance(stmt, Assign):
            if stmt.name.indexs is None:
                self.compile_expr(stmt.value)
                self.emit("STORE", stmt.name.name)
                return
            for index_expr in stmt.name.indexs:
                self.compile_expr(index_expr)
            self.compile_expr(stmt.value)
            self.emit("SET_INDEX", (stmt.name.name, len(stmt.name.indexs)))
            return

        if isinstance(stmt, Print):
            self.compile_expr(stmt.value)
            self.emit("PRINT")
            return

        if isinstance(stmt, If):
            self.compile_expr(stmt.condition)
            jump_if_false = self.emit("JUMP_IF_FALSE", -1)

            for then_stmt in stmt.then_body:
                self.compile_stmt(then_stmt)

            if stmt.else_body is not None:
                jump_to_end = self.emit("JUMP", -1)
                self.patch(jump_if_false, self.current())
                for else_stmt in stmt.else_body:
                    self.compile_stmt(else_stmt)
                self.patch(jump_to_end, self.current())
            else:
                self.patch(jump_if_false, self.current())
            return

        if isinstance(stmt, While):
            loop_start = self.current()
            self.compile_expr(stmt.condition)
            jump_if_false = self.emit("JUMP_IF_FALSE", -1)

            for body_stmt in stmt.body:
                self.compile_stmt(body_stmt)

            self.emit("JUMP", loop_start)
            self.patch(jump_if_false, self.current())
            return

        if isinstance(stmt, For):
            if stmt.init is not None:
                self.compile_stmt(stmt.init)

            loop_start = self.current()

            if stmt.condition is not None:
                self.compile_expr(stmt.condition)
            else:
                self.emit("PUSH", True)

            jump_if_false = self.emit("JUMP_IF_FALSE", -1)

            for body_stmt in stmt.body:
                self.compile_stmt(body_stmt)

            if stmt.update is not None:
                self.compile_stmt(stmt.update)

            self.emit("JUMP", loop_start)
            self.patch(jump_if_false, self.current())
            return

        if isinstance(stmt, Return):
            self.compile_expr(stmt.value)
            self.emit("RET")
            return

        if isinstance(stmt, FunctionDef):
            fn_compiler = Compiler()
            fn_compiler.functions = self.functions
            for body_stmt in stmt.body:
                fn_compiler.compile_stmt(body_stmt)
            fn_compiler.emit("PUSH", None)
            fn_compiler.emit("RET")
            self.functions[stmt.name] = FunctionInfo(
                params=[param.name for param in stmt.params],
                instructions=fn_compiler.instructions
            )
            return

        if isinstance(stmt, TryCatch):
            try_compiler = Compiler()
            try_compiler.functions = self.functions
            for s in stmt.try_body:
                try_compiler.compile_stmt(s)
            try_compiler.emit("PUSH", None)

            catch_compiler = Compiler()
            catch_compiler.functions = self.functions
            for s in stmt.catch_body:
                catch_compiler.compile_stmt(s)
            catch_compiler.emit("PUSH", None)

            self.emit(
                "TRY",
                {
                    "error_name": stmt.error_name,
                    "try_instructions": [
                        {"op": i.op, "arg": i.arg} for i in try_compiler.instructions
                    ],
                    "catch_instructions": [
                        {"op": i.op, "arg": i.arg} for i in catch_compiler.instructions
                    ],
                },
            )
            self.emit("POP")
            return

        if isinstance(stmt, ExprStmt):
            self.compile_expr(stmt.expr)
            self.emit("POP")
            return

        raise TypeError(f"Unsupported statement type: {type(stmt).__name__}")

    def compile_expr(self, expr: Expr) -> None:
        if isinstance(expr, Number):
            self.emit("PUSH", expr.value)
            return

        if isinstance(expr, FloatNumber):
            self.emit("PUSH", expr.value)
            return

        if isinstance(expr, BoolValue):
            self.emit("PUSH", expr.value)
            return

        if isinstance(expr, CharValue):
            self.emit("PUSH", expr.value)
            return

        if isinstance(expr, VoidValue):
            self.emit("PUSH", None)
            return

        if isinstance(expr, RangeExpr):
            if expr.start is None and expr.end is None:  # Optimization for full open range
                self.emit("PUSH", RangeValue(start=None, end=None))
                return
            if expr.start is None:
                self.emit("PUSH", None)
            else:
                self.compile_expr(expr.start)
            if expr.end is None:
                self.emit("PUSH", None)
            else:
                self.compile_expr(expr.end)
            self.emit("MAKE_RANGE")
            return

        if isinstance(expr, Var):
            self.emit("LOAD", expr.name)
            return

        if isinstance(expr, UnaryOp):
            self.compile_expr(expr.operand)
            if expr.op == "-":
                self.emit("NEG")
                return
            if expr.op == "!":
                self.emit("NOT")
                return
            raise ValueError(f"Unsupported unary operator: {expr.op}")

        if isinstance(expr, BinOp):
            self.compile_expr(expr.left)
            self.compile_expr(expr.right)

            op_map = {
                "+": "ADD",
                "-": "SUB",
                "*": "MUL",
                "/": "DIV",
                "%": "MOD",
                "^": "POW",
                "==": "EQ",
                "!=": "NE",
                ">": "GT",
                ">=": "GE",
                "<": "LT",
                "<=": "LE",
                "and": "AND",
                "or": "OR",
                "xor": "XOR",
            }
            opcode = op_map.get(expr.op)
            if opcode is None:
                raise ValueError(f"Unsupported binary operator: {expr.op}")
            self.emit(opcode)
            return

        if isinstance(expr, ArrayLiteral):
            for item in expr.values:
                self.compile_expr(item)
            self.emit("MAKE_LIST", len(expr.values))
            return

        if isinstance(expr, IndexAccess):
            self.compile_expr(expr.target)
            self.compile_expr(expr.index)
            self.emit("GET_INDEX", 1)
            return

        if isinstance(expr, Call):
            for arg in expr.args:
                self.compile_expr(arg)
            self.emit("CALL", {"name": expr.name, "argc": len(expr.args)})
            return

        raise TypeError(f"Unsupported expression type: {type(expr).__name__}")


def compile_program(program: Program) -> Bytecode:
    compiler = Compiler()
    return compiler.compile_program(program)
