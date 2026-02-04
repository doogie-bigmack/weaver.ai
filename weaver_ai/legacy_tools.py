from __future__ import annotations

import ast
import operator as op
import re
from typing import Any, ClassVar

from pydantic import BaseModel

from .mcp import MCPServer, ToolSpec


class Tool(BaseModel):
    name: str
    description: str
    required_scopes: list[str] = []

    def schema(self) -> dict:  # pragma: no cover - simple example
        return {}

    def call(self, **kwargs: Any) -> dict:
        raise NotImplementedError


class PythonEvalTool(Tool):
    name: str = "python_eval"
    description: str = "Evaluate simple arithmetic expressions"
    required_scopes: list[str] = ["tool:python_eval"]

    _ops: ClassVar[dict] = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.Mod: op.mod,
        ast.Pow: op.pow,
    }

    # Maximum expression length to prevent DoS
    MAX_EXPR_LENGTH: ClassVar[int] = 100
    # Maximum result value to prevent memory exhaustion
    MAX_RESULT: ClassVar[int] = 10**10
    # Valid characters in expression
    VALID_CHARS_PATTERN: ClassVar[str] = r"^[\d\s\+\-\*\/\%\(\)\.]+$"

    def call(self, expr: str) -> dict:
        # Input validation
        if not expr or not expr.strip():
            raise ValueError("Empty expression")

        if len(expr) > self.MAX_EXPR_LENGTH:
            raise ValueError(f"Expression too long (max {self.MAX_EXPR_LENGTH} chars)")

        # Check for valid characters only
        if not re.match(self.VALID_CHARS_PATTERN, expr):
            raise ValueError("Invalid characters in expression")

        # Check for dangerous patterns
        if any(danger in expr.lower() for danger in ["import", "exec", "eval", "__"]):
            raise ValueError("Potentially dangerous expression")

        try:
            node = ast.parse(expr, mode="eval")
            result = self._eval(node.body)

            # Validate result size
            if abs(result) > self.MAX_RESULT:
                raise ValueError(f"Result too large (max {self.MAX_RESULT})")

            return {"result": result}
        except (SyntaxError, TypeError) as e:
            raise ValueError(f"Invalid expression: {e}") from e

    def _eval(self, node: ast.AST) -> Any:
        if isinstance(node, ast.BinOp):
            left = self._eval(node.left)
            right = self._eval(node.right)

            # Prevent division by zero
            if isinstance(node.op, ast.Div) and right == 0:
                raise ValueError("Division by zero")

            # Prevent extremely large exponents
            if isinstance(node.op, ast.Pow):
                if abs(right) > 100:
                    raise ValueError("Exponent too large")

            op_func = self._ops.get(type(node.op))
            if not op_func:
                raise ValueError(f"Unsupported operation: {type(node.op).__name__}")

            return op_func(left, right)

        if isinstance(node, ast.Num):  # type: ignore[attr-defined]
            return node.n

        if isinstance(node, ast.Constant):  # Python 3.8+
            if isinstance(node.value, int | float):
                return node.value
            raise ValueError("Only numeric constants allowed")

        raise ValueError(f"Unsupported expression type: {type(node).__name__}")


def create_python_eval_server(server_id: str, key: str) -> MCPServer:
    # Use HS256 (symmetric key) for simplicity in tests, not RS256
    server = MCPServer(server_id, key, use_rs256=False, use_redis_nonces=False)
    tool = PythonEvalTool()
    spec = ToolSpec(
        name=tool.name, description=tool.description, input_schema={}, output_schema={}
    )
    server.add_tool(spec, lambda args: tool.call(expr=args["expr"]))
    return server
