"""Safe Math Expression Evaluator - A secure alternative to Python eval.

This module provides a safe way to evaluate mathematical expressions without
the security risks associated with eval() or exec().

OWASP References:
- A03:2021 – Injection
- A04:2021 – Insecure Design
"""

from __future__ import annotations

import ast
import math
import operator
from typing import Any, ClassVar

from pydantic import BaseModel


class SafeMathEvaluator(BaseModel):
    """Safe mathematical expression evaluator using AST parsing.

    This evaluator:
    - Only allows basic math operations
    - Prevents code injection
    - Has resource limits to prevent DoS
    - No access to Python builtins or imports
    """

    # Allowed operators (no exec, eval, or dangerous operations)
    ALLOWED_OPS: ClassVar[dict] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    # Allowed math functions (safe, deterministic functions only)
    ALLOWED_FUNCTIONS: ClassVar[dict] = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "floor": math.floor,
        "ceil": math.ceil,
    }

    # Allowed constants
    ALLOWED_CONSTANTS: ClassVar[dict] = {
        "pi": math.pi,
        "e": math.e,
        "tau": math.tau,
    }

    # Security limits
    MAX_EXPRESSION_LENGTH: ClassVar[int] = 500
    MAX_NUMBER_SIZE: ClassVar[float] = 1e100
    MAX_RECURSION_DEPTH: ClassVar[int] = 20
    MAX_RESULT_SIZE: ClassVar[float] = 1e100
    MAX_POWER_EXPONENT: ClassVar[float] = 1000

    def evaluate(self, expression: str) -> float | int:
        """Safely evaluate a mathematical expression.

        Args:
            expression: Mathematical expression to evaluate

        Returns:
            Result of the calculation

        Raises:
            ValueError: If expression is invalid or unsafe
            OverflowError: If result would be too large
        """
        # Input validation
        if not expression or not expression.strip():
            raise ValueError("Empty expression")

        if len(expression) > self.MAX_EXPRESSION_LENGTH:
            raise ValueError(
                f"Expression too long (max {self.MAX_EXPRESSION_LENGTH} chars)"
            )

        # Security check: No dangerous keywords
        dangerous_keywords = [
            "__",
            "import",
            "exec",
            "eval",
            "compile",
            "open",
            "file",
            "input",
            "raw_input",
            "execfile",
            "reload",
            "vars",
            "globals",
            "locals",
            "getattr",
            "setattr",
            "delattr",
            "classmethod",
            "staticmethod",
            "property",
            "super",
            "type",
            "isinstance",
            "issubclass",
            "callable",
            "format",
            "repr",
            "ascii",
            "ord",
            "chr",
            "bin",
            "hex",
            "oct",
            "dir",
            "help",
            "id",
            "hash",
            "object",
            "str",
            "bytes",
            "bytearray",
            "memoryview",
            "complex",
            "bool",
            "list",
            "tuple",
            "range",
            "dict",
            "set",
            "frozenset",
            "enumerate",
            "zip",
            "reversed",
            "sorted",
            "filter",
            "map",
            "all",
            "any",
            "iter",
            "next",
            "slice",
            "divmod",
            "pow",
            "compile",
            "exec",
            "eval",
        ]

        expression_lower = expression.lower()
        for keyword in dangerous_keywords:
            if keyword in expression_lower:
                raise ValueError(f"Forbidden keyword '{keyword}' in expression")

        try:
            # Parse the expression into an AST
            tree = ast.parse(expression, mode="eval")

            # Evaluate the AST safely
            result = self._eval_node(tree.body, depth=0)

            # Validate result
            if isinstance(result, (int, float)):
                if abs(result) > self.MAX_RESULT_SIZE:
                    raise OverflowError(
                        f"Result too large (max {self.MAX_RESULT_SIZE})"
                    )
                return result
            else:
                raise ValueError(f"Invalid result type: {type(result).__name__}")

        except SyntaxError as e:
            raise ValueError(f"Invalid syntax: {e}")
        except RecursionError:
            raise ValueError("Expression too complex (recursion limit exceeded)")

    def _eval_node(self, node: ast.AST, depth: int) -> Any:
        """Recursively evaluate an AST node.

        Args:
            node: AST node to evaluate
            depth: Current recursion depth

        Returns:
            Evaluated result

        Raises:
            ValueError: If node type is not allowed
        """
        # Check recursion depth
        if depth > self.MAX_RECURSION_DEPTH:
            raise ValueError(
                f"Expression too complex (max depth {self.MAX_RECURSION_DEPTH})"
            )

        # Numbers
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                if abs(node.value) > self.MAX_NUMBER_SIZE:
                    raise ValueError(f"Number too large (max {self.MAX_NUMBER_SIZE})")
                return node.value
            raise ValueError(
                f"Only numeric constants allowed, got {type(node.value).__name__}"
            )

        # For Python < 3.8 compatibility
        if isinstance(node, ast.Num):  # pragma: no cover
            if abs(node.n) > self.MAX_NUMBER_SIZE:
                raise ValueError(f"Number too large (max {self.MAX_NUMBER_SIZE})")
            return node.n

        # Names (constants and variables)
        if isinstance(node, ast.Name):
            if node.id in self.ALLOWED_CONSTANTS:
                return self.ALLOWED_CONSTANTS[node.id]
            raise ValueError(f"Unknown variable or constant: {node.id}")

        # Binary operations
        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left, depth + 1)
            right = self._eval_node(node.right, depth + 1)

            # Special validation for power operations
            if isinstance(node.op, ast.Pow):
                if abs(right) > self.MAX_POWER_EXPONENT:
                    raise ValueError(
                        f"Exponent too large (max {self.MAX_POWER_EXPONENT})"
                    )

            # Special validation for division
            if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
                if right == 0:
                    raise ValueError("Division by zero")

            op_func = self.ALLOWED_OPS.get(type(node.op))
            if op_func:
                try:
                    result = op_func(left, right)
                    if (
                        isinstance(result, (int, float))
                        and abs(result) > self.MAX_NUMBER_SIZE
                    ):
                        raise OverflowError(f"Intermediate result too large")
                    return result
                except OverflowError:
                    raise OverflowError("Mathematical operation resulted in overflow")
            else:
                raise ValueError(f"Unsupported operation: {type(node.op).__name__}")

        # Unary operations
        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand, depth + 1)
            op_func = self.ALLOWED_OPS.get(type(node.op))
            if op_func:
                return op_func(operand)
            else:
                raise ValueError(
                    f"Unsupported unary operation: {type(node.op).__name__}"
                )

        # Function calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                if func_name in self.ALLOWED_FUNCTIONS:
                    # Evaluate all arguments
                    args = [self._eval_node(arg, depth + 1) for arg in node.args]

                    # No keyword arguments allowed for simplicity
                    if node.keywords:
                        raise ValueError(
                            "Keyword arguments not supported in function calls"
                        )

                    try:
                        result = self.ALLOWED_FUNCTIONS[func_name](*args)
                        if (
                            isinstance(result, (int, float))
                            and abs(result) > self.MAX_NUMBER_SIZE
                        ):
                            raise OverflowError(f"Function result too large")
                        return result
                    except Exception as e:
                        raise ValueError(f"Error in function {func_name}: {e}")
                else:
                    raise ValueError(f"Function '{func_name}' is not allowed")
            else:
                raise ValueError("Complex function calls not supported")

        # Lists (for functions like sum, min, max)
        if isinstance(node, ast.List):
            return [self._eval_node(elem, depth + 1) for elem in node.elts]

        # Comparisons not allowed (could be used for information leakage)
        if isinstance(node, ast.Compare):
            raise ValueError("Comparison operations not allowed in math expressions")

        # Boolean operations not allowed
        if isinstance(node, ast.BoolOp):
            raise ValueError("Boolean operations not allowed in math expressions")

        # Any other node type is not allowed
        raise ValueError(f"Unsupported expression type: {type(node).__name__}")


def create_safe_math_server(server_id: str, key: str):
    """Create an MCP server with safe math evaluation.

    This is a secure replacement for create_python_eval_server.

    Args:
        server_id: Server identifier
        key: Authentication key

    Returns:
        MCPServer instance with safe math tool
    """
    from ..mcp import MCPServer, ToolSpec

    server = MCPServer(server_id, key)
    evaluator = SafeMathEvaluator()

    def safe_eval(args: dict) -> dict:
        """Wrapper for MCP tool interface."""
        try:
            expr = args.get("expr", "")
            result = evaluator.evaluate(expr)
            return {"result": result, "success": True}
        except Exception as e:
            return {"error": str(e), "success": False}

    spec = ToolSpec(
        name="safe_math_eval",
        description="Safely evaluate mathematical expressions",
        input_schema={
            "type": "object",
            "properties": {
                "expr": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate",
                }
            },
            "required": ["expr"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "result": {"type": "number"},
                "success": {"type": "boolean"},
                "error": {"type": "string"},
            },
        },
    )

    server.add_tool(spec, safe_eval)
    return server
